#!/usr/bin/env python3
"""把 pixiv_fetch.py 抓下来的 book.json 打包成可读的成品。

用法：
    python3 pixiv_build.py out              # 生成 md + html + epub
    python3 pixiv_build.py out --no-epub    # 只要 markdown 和 html
    python3 pixiv_build.py out --zip        # 额外打个压缩包到 out 旁边

产物：
    01_<章节名>.md …   单章 Markdown（标题下是该话封面）
    全集.md            全部章节合成一本
    index.html         手机浏览器阅读页
    <书名>.epub        手机阅读器用的电子书
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zipfile

CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0 auto;padding:18px 16px 80px;max-width:44rem;
 font-family:"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif;
 font-size:17px;line-height:1.9;background:#faf7f2;color:#222}
@media (prefers-color-scheme:dark){body{background:#16161a;color:#ddd}}
h1{font-size:1.45em;line-height:1.5;border-bottom:2px solid #d98c9c;padding-bottom:.4em}
h2{font-size:1.2em;margin-top:2.2em}
a{color:#b04a63}
.meta{font-size:.82em;color:#888;line-height:1.8;margin:.6em 0 1.4em}
.desc{font-size:.9em;background:rgba(180,120,140,.08);border-left:3px solid #d98c9c;
 padding:.7em 1em;margin:1em 0 1.6em;white-space:pre-wrap;line-height:1.7}
figure{margin:1.6em 0;text-align:center}
img{max-width:100%;height:auto;border-radius:6px;box-shadow:0 2px 14px rgba(0,0,0,.18)}
.chcover img{max-width:min(100%,340px)}
figcaption{font-size:.78em;color:#888;margin-top:.5em}
nav.toc{background:rgba(180,120,140,.07);padding:1em 1.2em;border-radius:10px;margin:1.5em 0}
nav.toc ol{margin:.4em 0 0;padding-left:1.4em}
nav.toc li{margin:.25em 0}
hr{border:0;border-top:1px solid rgba(150,150,150,.3);margin:2.2em 0}
.chapter{margin-top:3em}
.top{font-size:.78em;color:#888;text-align:right}
"""

EPUB_CSS = """body{font-family:serif;line-height:1.8;margin:1em}
h1{font-size:1.3em;margin:1em 0 .6em}
h2{font-size:1.1em;margin:1.6em 0 .5em}
.desc{font-size:.88em;color:#555;border-left:3px solid #c98;padding:.4em .8em;margin:1em 0;
white-space:pre-wrap}
p{margin:0 0 .2em}
figure{margin:1.2em 0;text-align:center}
img{max-width:100%}
.cover{text-align:center;margin:0 0 1.2em}
.coverpage{text-align:center;margin:0;padding:0}
.coverpage img{max-width:100%;max-height:100%}
.covernote{font-size:.78em;color:#999;text-align:center;margin:0 0 1em;
border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:.45em 0}
figcaption{font-size:.75em;color:#777}
.meta{font-size:.8em;color:#777;margin-bottom:1em}
hr{border:0;border-top:1px solid #ddd;margin:1.4em 0}
"""

RUBY = re.compile(r"\[\[rb:\s*(.+?)\s*>\s*(.+?)\]\]")
CHAPTER_TAG = re.compile(r"\[chapter:([^\]]*)\]")
NEWPAGE = "[newpage]"
IMG_LINE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def esc(s):
    return html.escape(s)


def slug(name, maxlen=60):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip().strip(".")
    return name[:maxlen] or "untitled"


def clean_text(content):
    """pixiv 正文里的行内标记 → 纯文本。"""
    s = RUBY.sub(r"\1", content)
    s = re.sub(r"\[jump:\d+\]", "", s)
    return s


def to_blocks(content):
    """把正文拆成块：p / img / h / hr。三种输出共用这一份解析。"""
    content = clean_text(content)
    blocks = []
    for seg_idx, seg in enumerate(content.split(NEWPAGE)):
        if seg_idx:
            blocks.append(("hr",))
        for line in seg.split("\n"):
            line = line.rstrip()
            cm = CHAPTER_TAG.fullmatch(line.strip())
            if cm:
                blocks.append(("h", cm.group(1).strip()))
                continue
            im = IMG_LINE.fullmatch(line.strip())
            if im:
                blocks.append(("img", im.group(1), im.group(2)))
                continue
            if not line.strip("\u3000 \t"):
                continue
            blocks.append(("p", line))
    return blocks


def to_markdown(content):
    content = clean_text(content)
    content = CHAPTER_TAG.sub(lambda m: f"\n\n## {m.group(1).strip()}\n\n", content)
    content = content.replace(NEWPAGE, "\n\n---\n\n")
    return re.sub(r"\n{3,}", "\n\n", content).strip("\n")


# ---------------------------------------------------------------- Markdown
def write_markdown(book, out_dir):
    series = book["series"]
    chapters = book["chapters"]
    written = []

    for c in chapters:
        lines = [f"# {c['title']}", ""]
        if c.get("cover"):
            lines += [f"![第{c['order']}话 封面]({c['cover']})", ""]
        lines.append(f"- pixiv 作品页：https://www.pixiv.net/novel/show.php?id={c['id']}")
        if c.get("date"):
            lines.append(f"- 发布日期：{c['date']}")
        if c.get("character_count"):
            lines.append(f"- 字数：{c['character_count']}")
        lines.append(f"- 标签：{'、'.join(c['tags']) if c.get('tags') else '（无）'}")
        if c.get("description"):
            lines += ["", "> " + "\n> ".join(c["description"].split("\n"))]
        lines += ["", "---", "", to_markdown(c["content"]), ""]
        path = os.path.join(out_dir, f"{c['order']:02d}_{slug(c['title'], 40)}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        written.append(path)

    full = [f"# {series['title']}", "",
            f"- 作者：{series['author']}"
            f"（https://www.pixiv.net/users/{series['author_id']}）",
            f"- 系列页：{series['url']}",
            f"- 共 {len(chapters)} 话", ""]
    if series.get("caption"):
        full += ["> " + series["caption"].replace("\n", "\n> "), ""]
    if series.get("cover"):
        full += [f"![系列封面]({series['cover']})", ""]
    full += ["## 目录", ""]
    full += [f"{c['order']}. {c['title']}" for c in chapters]
    full.append("")
    for c in chapters:
        full += ["---", "", f"# 第{c['order']}话 {c['title']}", ""]
        if c.get("cover"):
            full += [f"![第{c['order']}话 封面]({c['cover']})", ""]
        if c.get("description"):
            full += ["> " + "\n> ".join(c["description"].split("\n")), ""]
        full += [to_markdown(c["content"]), ""]
    with open(os.path.join(out_dir, "全集.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(full))
    return written


# ---------------------------------------------------------------- HTML
def blocks_to_html(blocks, img_prefix=""):
    out = []
    for b in blocks:
        if b[0] == "p":
            out.append(f"<p>{esc(b[1])}</p>")
        elif b[0] == "img":
            src = img_prefix + b[2]
            out.append(f'<figure><img src="{esc(src)}" alt="{esc(b[1])}">'
                       f"<figcaption>{esc(b[1])}</figcaption></figure>")
        elif b[0] == "h":
            out.append(f"<h3>{esc(b[1])}</h3>")
        elif b[0] == "hr":
            out.append('<hr class="pagebreak">')
    return "\n".join(out)


def write_html(book, out_dir, fetched_at=""):
    series = book["series"]
    chapters = book["chapters"]
    p = [f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(series['title'])} - pixiv小説</title>
<style>{CSS}</style></head><body>
<h1>{esc(series['title'])}</h1>
<div class="meta">作者：{esc(series['author'])}<br>
pixiv 系列：<a href="{series['url']}">{series['url']}</a><br>
全 {len(chapters)} 话{(' · 抓取于 ' + fetched_at[:10]) if fetched_at else ''}</div>"""]
    if series.get("cover"):
        p.append(f'<div style="text-align:center"><img src="{esc(series["cover"])}" alt="封面"></div>')
    p.append('<nav class="toc" id="toc"><strong>目录</strong><ol>')
    for c in chapters:
        p.append(f'<li><a href="#ch{c["order"]}">{esc(c["title"])}</a></li>')
    p.append("</ol></nav>")
    for c in chapters:
        p.append(f'<section class="chapter" id="ch{c["order"]}">')
        p.append(f'<h2>{c["order"]}. {esc(c["title"])}</h2>')
        if c.get("cover"):
            p.append(f'<figure class="chcover"><img src="{esc(c["cover"])}" '
                     f'alt="第{c["order"]}话 封面"><figcaption>第{c["order"]}话 封面</figcaption></figure>')
        p.append(f'<div class="meta"><a href="https://www.pixiv.net/novel/show.php?id='
                 f'{c["id"]}">pixiv 原文</a></div>')
        if c.get("description"):
            p.append(f'<div class="desc">{esc(c["description"])}</div>')
        p.append(blocks_to_html(to_blocks(c["content"])))
        p.append("</section>")
    p.append('<p class="top"><a href="#toc">↑ 返回目录</a></p></body></html>')
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(p))


# ---------------------------------------------------------------- EPUB
FRONT = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja" lang="ja">
<head><meta charset="utf-8"/><title>表紙</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
<div class="coverpage"><img src="../images/cover%s" alt="封面"/></div>
</body></html>"""


def write_epub(book, out_dir):
    series = book["series"]
    chapters = book["chapters"]
    build = os.path.join(out_dir, ".epub_build")
    if os.path.isdir(build):
        shutil.rmtree(build)
    for d in ("META-INF", "OEBPS/images", "OEBPS/text"):
        os.makedirs(os.path.join(build, d), exist_ok=True)

    # 封面
    cover_ext = ".jpg"
    if series.get("cover"):
        cover_ext = os.path.splitext(series["cover"])[1] or ".jpg"
        shutil.copy(os.path.join(out_dir, series["cover"]),
                    os.path.join(build, "OEBPS/images", "cover" + cover_ext))
    with open(os.path.join(build, "OEBPS/text/front.xhtml"), "w", encoding="utf-8") as f:
        f.write(FRONT % cover_ext)
    with open(os.path.join(build, "OEBPS/text/style.css"), "w", encoding="utf-8") as f:
        f.write(EPUB_CSS)

    used = {}
    seen_covers = {}
    for c in chapters:
        o = c["order"]
        blocks = to_blocks(c["content"])
        paras = []
        for b in blocks:
            if b[0] == "img":
                src = os.path.join(out_dir, b[2])
                fn = os.path.basename(b[2])
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(build, "OEBPS/images", fn))
                    used[fn] = True
                paras.append(f'<figure><img src="../images/{fn}" alt="{esc(b[1])}"/>'
                             f"<figcaption>{esc(b[1])}</figcaption></figure>")
            elif b[0] == "h":
                paras.append(f"<h2>{esc(b[1])}</h2>")
            elif b[0] == "hr":
                paras.append("<hr/>")
            else:
                paras.append(f"<p>{esc(b[1])}</p>")

        cover_html = ""
        if c.get("cover") and os.path.exists(os.path.join(out_dir, c["cover"])):
            with open(os.path.join(out_dir, c["cover"]), "rb") as fh:
                h = hashlib.md5(fh.read()).hexdigest()
            if h in seen_covers:
                # 同一张封面在系列里重复出现时不再贴图，免得连着两页一样
                cover_html = f'<p class="covernote">封面同前（第{seen_covers[h]}话）</p>'
            else:
                seen_covers[h] = o
                ext = os.path.splitext(c["cover"])[1]
                cfn = f"ch{o:02d}_cover{ext}"
                shutil.copy(os.path.join(out_dir, c["cover"]),
                            os.path.join(build, "OEBPS/images", cfn))
                used[cfn] = True
                cover_html = f'<div class="cover"><img src="../images/{cfn}" alt="第{o}话 封面"/></div>'

        xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja" lang="ja">
<head><meta charset="utf-8"/><title>{esc(c['title'])}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
<h1>{o}. {esc(c['title'])}</h1>
{cover_html}
<p class="meta">pixiv: novel/show.php?id={c['id']}</p>
{('<div class="desc">' + esc(c['description']) + '</div>') if c.get('description') else ''}
{chr(10).join(paras)}
</body></html>"""
        with open(os.path.join(build, f"OEBPS/text/ch{o:02d}.xhtml"), "w", encoding="utf-8") as f:
            f.write(xhtml)

    uid = hashlib.md5(f"{series['id']}".encode()).hexdigest()
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="text/style.css" media-type="text/css"/>',
                f'<item id="cover-img" href="images/cover{cover_ext}" media-type="image/'
                f'{"png" if cover_ext == ".png" else "jpeg"}" properties="cover-image"/>',
                '<item id="front" href="text/front.xhtml" media-type="application/xhtml+xml"/>']
    spine = ['<itemref idref="front"/>']
    for c in chapters:
        manifest.append(f'<item id="ch{c["order"]:02d}" href="text/ch{c["order"]:02d}.xhtml" '
                        f'media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="ch{c["order"]:02d}"/>')
    for fn in sorted(used):
        iid = "img_" + re.sub(r"\W", "_", os.path.splitext(fn)[0])
        mt = "image/png" if fn.endswith(".png") else "image/jpeg"
        manifest.append(f'<item id="{iid}" href="images/{fn}" media-type="{mt}"/>')

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">urn:uuid:{uid}</dc:identifier>
<dc:title>{esc(series['title'])}</dc:title>
<dc:creator>{esc(series['author'])}</dc:creator>
<dc:language>ja</dc:language>
<dc:source>{esc(series['url'])}</dc:source>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx">
{chr(10).join(spine)}
</spine>
</package>"""
    with open(os.path.join(build, "OEBPS/content.opf"), "w", encoding="utf-8") as f:
        f.write(opf)

    nav = ['<?xml version="1.0" encoding="utf-8"?>',
           '<!DOCTYPE html>',
           '<html xmlns="http://www.w3.org/1999/xhtml" '
           'xmlns:epub="http://www.idpf.org/2007/ops" lang="ja">',
           '<head><meta charset="utf-8"/><title>目次</title></head><body>',
           '<nav epub:type="toc" id="toc"><h1>目次</h1><ol>']
    for c in chapters:
        nav.append(f'<li><a href="text/ch{c["order"]:02d}.xhtml">{esc(c["title"])}</a></li>')
    nav.append("</ol></nav></body></html>")
    with open(os.path.join(build, "OEBPS/nav.xhtml"), "w", encoding="utf-8") as f:
        f.write("\n".join(nav))

    pts = "".join(f'<navPoint id="np{c["order"]}" playOrder="{c["order"]}">'
                  f'<navLabel><text>{esc(c["title"])}</text></navLabel>'
                  f'<content src="text/ch{c["order"]:02d}.xhtml"/></navPoint>'
                  for c in chapters)
    ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="urn:uuid:{uid}"/></head>
<docTitle><text>{esc(series['title'])}</text></docTitle>
<navMap>{pts}</navMap></ncx>"""
    with open(os.path.join(build, "OEBPS/toc.ncx"), "w", encoding="utf-8") as f:
        f.write(ncx)

    with open(os.path.join(build, "META-INF/container.xml"), "w", encoding="utf-8") as f:
        f.write("""<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf"
 media-type="application/oebps-package+xml"/></rootfiles></container>""")

    epub_path = os.path.join(out_dir, f"{slug(series['title'], 60)}.epub")
    with zipfile.ZipFile(epub_path, "w") as z:
        # mimetype 必须是第一个条目且不压缩，否则阅读器会认不出
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for base, _, files in os.walk(build):
            for fn in sorted(files):
                full = os.path.join(base, fn)
                z.write(full, os.path.relpath(full, build),
                        compress_type=zipfile.ZIP_DEFLATED)
    shutil.rmtree(build)
    return epub_path


def main():
    ap = argparse.ArgumentParser(description="把 book.json 打包成 md / html / epub")
    ap.add_argument("out_dir", nargs="?", default="out")
    ap.add_argument("--no-md", action="store_true")
    ap.add_argument("--no-html", action="store_true")
    ap.add_argument("--no-epub", action="store_true")
    ap.add_argument("--zip", action="store_true", help="额外生成压缩包")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    with open(os.path.join(out_dir, "book.json"), encoding="utf-8") as f:
        book = json.load(f)

    made = []
    if not args.no_md:
        write_markdown(book, out_dir)
        made.append("markdown")
    if not args.no_html:
        write_html(book, out_dir, book.get("fetched_at", ""))
        made.append("html")
    if not args.no_epub:
        made.append(write_epub(book, out_dir))

    if args.zip:
        zp = out_dir.rstrip(os.sep) + ".zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(out_dir):
                for fn in files:
                    full = os.path.join(base, fn)
                    z.write(full, os.path.relpath(full, os.path.dirname(out_dir)))
        made.append(zp)

    print("生成：\n  " + "\n  ".join(str(m) for m in made))
    return 0


if __name__ == "__main__":
    sys.exit(main())
