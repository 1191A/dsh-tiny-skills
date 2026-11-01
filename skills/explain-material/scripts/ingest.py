#!/usr/bin/env python3
"""ingest — 把任意材料转成 AI 好读的形式（md + 图片）。

用法:
    python3 ingest.py <文件> [-o 输出目录] [--asr] [--model small]

产出:
    <输出目录>/source.md      带页码 / 幻灯片号 / 时间戳的正文
    <输出目录>/images/        抽出来的图（公式、版面、视频帧）

设计原则:
    1. 宁可不转，不可乱编。读不到的部分写进"提取报告"，不猜。
    2. 每个段落都能对回原位置（[s12] / [p3] / [00:01:23]），
       这样下游引用原话时才有据可依。
    3. 缺依赖只降级，不报错退出。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ---------- 小工具 ----------

def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=900)
        return p.stdout.decode("utf-8", "replace")
    except Exception:
        return ""


BOILER = ("单击此处", "母版", "第二级", "第三级", "第四级", "第五级")


def is_boilerplate(t: str) -> bool:
    """过滤 PPT 母版占位符这类没有信息量的文字。"""
    return any(b in t for b in BOILER)


def clean(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()


# ---------- PPT 渲染（POI / Java） ----------

POI_DIR = Path(__file__).resolve().parent / "poi"


def ppt_render(path: Path, outdir: Path, scale: str = "2.0"):
    """用 Apache POI 把 .ppt 逐页渲染成 PNG，并拿到每页文字。"""
    warnings = []
    if not have("java"):
        return None, [], ["缺 java（apt install default-jdk-headless），无法渲染幻灯片"]
    if not (POI_DIR / "poi.jar").exists():
        return None, [], ["找不到 POI 依赖，无法渲染"]

    imgdir = outdir / "images"
    imgdir.mkdir(parents=True, exist_ok=True)
    cp = "%s:%s" % (POI_DIR, POI_DIR / "*")
    proc = subprocess.run(
        ["java", "-Djava.awt.headless=true", "-cp", cp, "RenderPpt",
         str(path.resolve()), str(imgdir.resolve()), scale],
        capture_output=True, timeout=1800, cwd=str(POI_DIR),
    )
    tsv = imgdir / "text.tsv"
    if proc.returncode != 0 or not tsv.exists():
        msg = proc.stderr.decode("utf-8", "replace")[-300:]
        return None, [], ["幻灯片渲染失败: %s" % msg]

    blocks = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        tag, text = line.split("\t", 1)
        text = text.replace(" ⏎ ", "\n").strip()
        png = imgdir / (tag + ".png")
        body = text if text else "（本页以图为主）"
        body += "\n\n![%s](images/%s.png)" % (tag, tag)
        blocks.append((tag, body))
        if not png.exists():
            warnings.append("%s 的图没生成" % tag)

    images = sorted(imgdir.glob("s*.png"))
    tsv.unlink(missing_ok=True)
    if not blocks:
        return None, [], ["渲染完成但没解析出任何页"]
    return blocks, images, warnings


# ---------- PPT 97-2003 ----------

TEXT_CHARS_ATOM = b"\xa0\x0f"
TEXT_BYTES_ATOM = b"\xa8\x0f"


def ppt_extract(path: Path, outdir: Path):
    """返回 (段落列表, 图片路径列表, 警告)"""
    import olefile

    warnings = []
    paras = []
    images = []
    ole = olefile.OleFileIO(str(path))

    if ole.exists("PowerPoint Document"):
        data = ole.openstream("PowerPoint Document").read()
        i = 0
        while True:
            j = data.find(TEXT_CHARS_ATOM, i)
            if j < 0:
                break
            if j >= 2:
                ln = int.from_bytes(data[j + 2:j + 6], "little")
                if 0 < ln < 20000 and j + 6 + ln <= len(data):
                    raw = data[j + 6:j + 6 + ln]
                    txt = raw.decode("utf-16-le", "ignore")
                    txt = clean(txt)
                    if txt and not is_boilerplate(txt) and re.search(r"\w", txt):
                        paras.append(txt)
            i = j + 2
    else:
        warnings.append("没有 PowerPoint Document 流，可能不是标准 ppt")

    # 图片：Pictures 流里按魔数切出来
    if ole.exists("Pictures"):
        blob = ole.openstream("Pictures").read()
        images = carve_images(blob, outdir)
    ole.close()

    if not paras:
        warnings.append("没有抽到文字")
    if not images:
        warnings.append("没有在 Pictures 流里找到图片（公式多半是 EMF/OLE 对象，未渲染）")
    else:
        warnings.append("只抽到了位图；公式若是 EMF 矢量对象则仍未渲染，"
                        "需要精确公式请在手机 WPS 里另存为 PDF 再跑一遍")
    return paras, images, warnings


def carve_images(blob: bytes, outdir: Path):
    imgdir = outdir / "images"
    imgdir.mkdir(parents=True, exist_ok=True)
    out = []
    n = 0

    for m in re.finditer(b"\x89PNG\r\n\x1a\n", blob):
        start = m.start()
        end = blob.find(b"IEND\xaeB`\x82", start)
        if end < 0:
            continue
        end += 8
        if end - start < 3000:      # 图标之类太小，多半没信息
            continue
        n += 1
        p = imgdir / f"img{n:03d}.png"
        p.write_bytes(blob[start:end])
        out.append(p)

    for m in re.finditer(b"\xff\xd8\xff", blob):
        start = m.start()
        end = blob.find(b"\xff\xd9", start + 3)
        if end < 0:
            continue
        end += 2
        if end - start < 3000:
            continue
        n += 1
        p = imgdir / f"img{n:03d}.jpg"
        p.write_bytes(blob[start:end])
        out.append(p)

    return out


# ---------- PPTX ----------

def pptx_extract(path: Path, outdir: Path):
    warnings = []
    paras = []
    images = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        slides = sorted(
            [n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)],
            key=lambda n: int(re.search(r"slide(\d+)", n).group(1)),
        )
        for idx, name in enumerate(slides, 1):
            xml = z.read(name).decode("utf-8", "ignore")
            texts = [clean(t) for t in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S)]
            texts = [t for t in texts if t]
            if texts:
                paras.append(("[s%d]" % idx, "\n".join(texts)))
            else:
                paras.append(("[s%d]" % idx, "（本页没有文字，只有图）"))

        imgdir = outdir / "images"
        media = [n for n in names if n.startswith("ppt/media/")]
        for n in media:
            if not re.search(r"\.(png|jpg|jpeg|emf|wmf|gif|svg)$", n, re.I):
                continue
            imgdir.mkdir(parents=True, exist_ok=True)
            dest = imgdir / Path(n).name
            dest.write_bytes(z.read(n))
            images.append(dest)

    if not paras:
        warnings.append("没有抽到幻灯片文字")
    return [(t if isinstance(t, str) else t[1]) for t in paras], images, warnings, paras


# ---------- PDF ----------

def pdf_extract(path: Path, outdir: Path, dpi: int = 120):
    warnings = []
    paras = []
    images = []

    if not have("pdftotext"):
        warnings.append("缺 pdftotext（apt install poppler-utils），PDF 文字没读")
        return paras, images, warnings

    txt = run(["pdftotext", "-layout", str(path), "-"])
    pages = txt.split("\f")
    # pdftotext 末尾会多出一个空段，按 pdfinfo 的真实页数裁掉
    n_real = 0
    if have("pdfinfo"):
        info = run(["pdfinfo", str(path)])
        m = re.search(r"Pages:\s+(\d+)", info)
        if m:
            n_real = int(m.group(1))
    if n_real and len(pages) > n_real:
        pages = pages[:n_real]
    for i, page in enumerate(pages, 1):
        page = clean(page)
        if page:
            paras.append(("[p%d]" % i, page))
        else:
            paras.append(("[p%d]" % i, "（本页没有文字层，已转成图片）"))

    # 转图：文字稀少的页才转，省时间
    if have("pdftoppm"):
        imgdir = outdir / "images"
        imgdir.mkdir(parents=True, exist_ok=True)
        empty = [i for i, p in enumerate(pages, 1) if len(p.strip()) < 30]
        for i in empty[:60]:
            run(["pdftoppm", "-f", str(i), "-l", str(i), "-r", str(dpi),
                 "-png", "-singlefile", str(path), str(imgdir / f"p{i:03d}")])
            p = imgdir / f"p{i:03d}.png"
            if p.exists():
                images.append(p)
        if empty:
            warnings.append("%d 页没有文字层，已转图由视觉模型读" % len(empty))
        if len(pages) > 1 and not empty:
            warnings.append("全部页都有文字层；公式可能仍是乱码，必要时加 --render 全页转图")

    return paras, images, warnings


# ---------- DOCX / XLSX ----------

def docx_extract(path: Path, outdir: Path):
    warnings = []
    paras = []
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"'))
    for line in clean(text).split("\n"):
        if line.strip():
            paras.append(line.strip())
    images = []
    try:
        with zipfile.ZipFile(path) as z:
            imgdir = outdir / "images"
            for n in z.namelist():
                if n.startswith("word/media/"):
                    imgdir.mkdir(parents=True, exist_ok=True)
                    (imgdir / Path(n).name).write_bytes(z.read(n))
                    images.append(imgdir / Path(n).name)
    except Exception:
        pass
    if not paras:
        warnings.append("没有抽到正文")
    return paras, images, warnings


def xlsx_extract(path: Path, outdir: Path):
    warnings = []
    paras = []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True)
        for ws in wb.worksheets:
            lines = []
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" | ".join(cells))
            if lines:
                paras.append(("[%s]" % ws.title, "\n".join(lines)))
    except ImportError:
        warnings.append("缺 openpyxl（pip install openpyxl），只抽了共享字符串")
        with zipfile.ZipFile(path) as z:
            if "xl/sharedStrings.xml" in z.namelist():
                xml = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
                strs = re.findall(r"<t[^>]*>(.*?)</t>", xml, re.S)
                paras = [s for s in strs if s.strip()]
    return paras, [], warnings


# ---------- 视频 / 音频 ----------

def media_extract(path: Path, outdir: Path, want_asr=False, model="small"):
    warnings = []
    images = []
    paras = []

    if not have("ffprobe"):
        warnings.append("缺 ffprobe（apt install ffmpeg），视频没读")
        return paras, images, warnings

    meta = run(["ffprobe", "-v", "error", "-show_entries",
                "format=duration,size:stream=codec_type,width,height",
                "-of", "default=nw=1", str(path)])
    dur = 0.0
    m = re.search(r"duration=([\d.]+)", meta)
    if m:
        dur = float(m.group(1))
    paras.append(("", "视频时长 %.0f 秒" % dur if dur else "媒体信息:\n" + meta))

    # 抽帧
    if have("ffmpeg") and dur > 0:
        imgdir = outdir / "images"
        imgdir.mkdir(parents=True, exist_ok=True)
        n = max(3, min(24, int(dur // 30) + 3))
        step = dur / (n + 1)
        for k in range(1, n + 1):
            t = step * k
            out = imgdir / ("f%02d.png" % k)
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % t,
                 "-i", str(path), "-frames:v", "1",
                 "-vf", "scale=1280:-2", str(out)])
            if out.exists():
                images.append(out)
                paras.append(("[%02d:%02d]" % (t // 60, t % 60),
                              "（第 %d 帧，见 %s）" % (k, out.name)))

    if want_asr:
        paras_asr, warn = asr_extract(path, outdir, model)
        paras.extend(paras_asr)
        warnings.extend(warn)
    else:
        warnings.append("没有转写语音（加 --asr 开启；只抽了画面）")

    return paras, images, warnings


def asr_extract(path: Path, outdir: Path, model="small"):
    warnings = []
    try:
        import wave
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError:
        return [], ["缺 faster-whisper（pip install faster-whisper），语音没转写"]

    wav = outdir / "_audio.wav"
    if not have("ffmpeg"):
        return [], ["缺 ffmpeg，抽不出音轨"]
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
         "-ar", "16000", "-ac", "1", str(wav)])
    if not wav.exists():
        return [], ["抽音轨失败（可能没有音轨）"]

    try:
        w = wave.open(str(wav), "rb")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        audio = data.astype(np.float32) / 32768.0
        w.close()
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, info = m.transcribe(audio, vad_filter=True)
        out = []
        for s in segs:
            out.append(("[%02d:%02d]" % (s.start // 60, s.start % 60), s.text.strip()))
        if not out:
            warnings.append("音轨里没检测到人声")
        return out, warnings
    except Exception as e:
        return [], ["转写失败: %s" % e]


# ---------- 主流程 ----------

def ingest(src: Path, outdir: Path, want_asr=False, model="small"):
    outdir.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()
    warnings: list[str] = []
    blocks: list[tuple[str, str]] = []
    images: list[Path] = []

    if ext == ".ppt":
        rblocks, images, warnings = ppt_render(src, outdir)
        if rblocks:
            blocks = rblocks
            warnings.append("已逐页渲染成图：文字来自 ppt 文本层，公式和图形在图片里，"
                            "需要时用视觉读 images/sNNN.png")
        else:
            paras, images2, w2 = ppt_extract(src, outdir)
            blocks = [("", p) for p in paras]
            images = images2
            warnings += w2
            warnings.append("渲染不可用，退回纯文字提取，公式读不到")
    elif ext == ".pptx":
        _, images, warnings, numbered = pptx_extract(src, outdir)
        blocks = numbered
    elif ext == ".pdf":
        blocks, images, warnings = pdf_extract(src, outdir)
    elif ext == ".docx":
        paras, images, warnings = docx_extract(src, outdir)
        blocks = [("", p) for p in paras]
    elif ext in (".xlsx", ".xlsm"):
        blocks, images, warnings = xlsx_extract(src, outdir)
    elif ext in (".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v",
                 ".mp3", ".wav", ".m4a", ".aac", ".flac"):
        blocks, images, warnings = media_extract(src, outdir, want_asr, model)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        imgdir = outdir / "images"
        imgdir.mkdir(parents=True, exist_ok=True)
        dest = imgdir / src.name
        shutil.copy2(src, dest)
        images = [dest]
        blocks = [("", "（整份材料是一张图，见 images/%s）" % src.name)]
        warnings.append("图片内容没有转成文字，交给视觉模型直接读")
    elif ext in (".txt", ".md"):
        blocks = [("", src.read_text(encoding="utf-8", errors="replace"))]
    else:
        warnings.append("不认识的格式: %s" % ext)
        try:
            blocks = [("", src.read_text(encoding="utf-8", errors="replace")[:20000])]
        except Exception:
            pass

    # 写 md
    lines = ["# 材料: %s" % src.name, "", "## 提取报告", ""]
    lines.append("- 格式: `%s`，大小 %.1f MB" % (ext, src.stat().st_size / 1048576))
    lines.append("- 文字块: %d 段" % len([b for b in blocks if b[1].strip()]))
    lines.append("- 图片: %d 张" % len(images))
    for w in warnings:
        lines.append("- ⚠️ %s" % w)
    lines.append("")
    lines.append("## 正文")
    lines.append("")
    for tag, body in blocks:
        body = clean(body)
        if not body:
            continue
        if tag:
            lines.append("### %s" % tag)
        lines.append(body)
        lines.append("")

    md = outdir / "source.md"
    md.write_text("\n".join(lines), encoding="utf-8")

    # 给人看的版本：一页一节，文字在上、图在下，开头带目录
    notes = outdir / "讲义.md"
    notes.write_text(build_notes(src, blocks), encoding="utf-8")

    return md, warnings, len(images)


def build_notes(src: Path, blocks) -> str:
    """把抽取结果排成一份能直接读的稿子：目录 + 每页文字 + 该页的图。"""
    out = ["# %s" % src.stem, "", "> 由 `%s` 整理 · 图在 `images/`" % src.name, "", "## 目录", ""]
    titles = []
    for tag, body in blocks:
        first = ""
        for line in body.split("\n"):
            line = line.strip()
            if line and not line.startswith("!["):
                first = line[:40]
                break
        titles.append((tag, first or "（图）"))
    for i, (tag, first) in enumerate(titles, 1):
        out.append("%d. %s%s" % (i, first, ("  ·  " + tag) if tag else ""))
    out.append("")
    for i, (tag, body) in enumerate(blocks, 1):
        title = titles[i - 1][1]
        out.append("## %d · %s" % (i, title))
        out.append("")
        out.append(body.strip())
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="把材料转成 AI 好读的 md + 图片")
    ap.add_argument("file")
    ap.add_argument("-o", "--out", default=None, help="输出目录（默认 <文件名>_ingest）")
    ap.add_argument("--asr", action="store_true", help="视频/音频同时转写语音")
    ap.add_argument("--model", default="small", help="whisper 模型: tiny/base/small/medium")
    a = ap.parse_args()

    src = Path(a.file).expanduser()
    if not src.exists():
        sys.exit("找不到文件: %s" % src)
    outdir = Path(a.out) if a.out else src.with_name(src.stem + "_ingest")

    md, warnings, nimg = ingest(src, outdir, a.asr, a.model)
    print("输出: %s" % md)
    print("图片: %d 张 -> %s" % (nimg, outdir / "images"))
    for w in warnings:
        print("⚠️  %s" % w)


if __name__ == "__main__":
    main()
