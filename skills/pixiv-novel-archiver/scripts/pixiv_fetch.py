#!/usr/bin/env python3
"""抓取一个 pixiv 小说系列：系列信息、全部章节正文、正文插图、封面。

用法：
    python3 pixiv_fetch.py 1280985 -o out
    python3 pixiv_fetch.py https://www.pixiv.net/novel/series/1280985 -o out

产物（都写在 -o 目录里）：
    book.json      结构化数据（含每章正文，图片已替换成本地路径）
    covers/        系列封面 + 各话封面
    images/        正文插图原图
"""

import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

BASE = "https://www.pixiv.net"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Referer": BASE + "/", "Accept": "*/*"}
CTX = ssl.create_default_context()
PAGE_LIMIT = 10          # series_content 的 limit 上限就是 10
IMG_TAG = re.compile(r"\[pixivimage:([^\]]+)\]")


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def fetch(url, binary=False, tries=5, backoff=1.5):
    """带重试的 GET。手机网络/代理经常在 TLS 握手上抽风，所以要重试。"""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            body = urllib.request.urlopen(req, timeout=40, context=CTX).read()
            return body if binary else body.decode("utf-8")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(backoff * (i + 1))
    raise last


def getjson(url):
    return json.loads(fetch(url))


def slug(name, maxlen=60):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip().strip(".")
    return name[:maxlen] or "untitled"


def series_id_of(arg):
    m = re.search(r"/novel/series/(\d+)", arg)
    if m:
        return m.group(1)
    if arg.isdigit():
        return arg
    raise SystemExit(f"看不懂这个参数：{arg}")


def download(url, path, tries=4):
    """下载图片，返回实际落盘路径（原图可能是 png，会自动换后缀）。"""
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    candidates = [url]
    if url.endswith(".jpg"):
        candidates.append(url[:-4] + ".png")
    for cand in candidates:
        for i in range(tries):
            try:
                data = fetch(cand, binary=True)
                if len(data) < 500:
                    raise ValueError("响应太小，可能不是图片")
                real = path
                if os.path.splitext(cand)[1] != os.path.splitext(path)[1]:
                    real = os.path.splitext(path)[0] + os.path.splitext(cand)[1]
                os.makedirs(os.path.dirname(real), exist_ok=True)
                with open(real, "wb") as f:
                    f.write(data)
                return real
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break          # 换下一个候选 URL
                time.sleep(1.0 * (i + 1))
            except Exception:      # noqa: BLE001
                time.sleep(1.0 * (i + 1))
    return None


def series_meta(sid):
    return getjson(f"{BASE}/ajax/novel/series/{sid}")["body"]


def episodes(sid):
    """分页取章节列表。注意：加上 =lang= 参数会 400，limit 必须 <= 10。"""
    out, last = [], 0
    while True:
        body = getjson(f"{BASE}/ajax/novel/series_content/{sid}"
                       f"?last_order={last}&limit={PAGE_LIMIT}")["body"]
        items = body["thumbnails"]["novel"]
        if not items:
            break
        for n in items:
            out.append({
                "order": n["seriesContentOrder"],
                "id": str(n["id"]),
                "title": n["title"],
                "date": n.get("createDate", ""),
                "tags": n.get("tags") or [],
                "text_count": n.get("textCount", 0),
                "cover_url": n["url"],
            })
        last = items[-1]["seriesContentOrder"]
        if not body["page"].get("nextPage"):
            break
        time.sleep(0.3)
    out.sort(key=lambda x: x["order"])
    return out


def illust_info(iid, cache):
    if iid not in cache:
        try:
            cache[iid] = getjson(f"{BASE}/ajax/illust/{iid}")["body"]
        except Exception as e:  # noqa: BLE001
            log(f"  ! 插图 {iid} 信息获取失败：{e}")
            cache[iid] = None
    return cache[iid]


def localize_content(content, out_dir, order, img_dir, cache, missing):
    """把 [pixivimage:id-page] 换成 Markdown 图片引用，并下载原图。"""
    def repl(m):
        token = m.group(1)
        mm = re.match(r"^(\d+)(?:-(\d+))?$", token)
        if not mm:
            return m.group(0)
        iid, page = mm.group(1), int(mm.group(2) or 1)
        info = illust_info(iid, cache)
        if not info:
            missing.append(token)
            return f"\n> （插图 {iid} 获取失败）\n"
        orig = info["urls"]["original"]
        ext = os.path.splitext(orig)[1] or ".jpg"
        stem = orig.rsplit("_p", 1)[0]
        # 原图文件名是 p0 起，pixiv 正文里的页码是 1 起
        url = f"{stem}_p{page - 1}{ext}"
        fname = f"{order:02d}_illust_{iid}_p{page}{ext}"
        path = os.path.join(img_dir, fname)
        saved = download(url, path)
        if not saved:  # 原图档有时被作者删了，退回 master1200
            fallback = url.replace("/img-original/", "/img-master/")
            fallback = fallback[: -len(ext)] + "_master1200" + ext
            saved = download(fallback, path)
        if not saved:
            missing.append(token)
            return f"\n> （插图 {iid} 下载失败）\n"
        title = slug(info.get("title") or "illust", 40)
        rel = os.path.relpath(saved, out_dir).replace(os.sep, "/")
        return f"\n\n![{title}]({rel})\n\n"

    return IMG_TAG.sub(repl, content)


def clean_description(html_text):
    s = html_text or ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<a [^>]*>(.*?)</a>", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def main():
    ap = argparse.ArgumentParser(description="抓取 pixiv 小说系列")
    ap.add_argument("series", help="系列 ID 或 https://www.pixiv.net/novel/series/<id>")
    ap.add_argument("-o", "--out", default="out", help="输出目录（默认 ./out）")
    ap.add_argument("--delay", type=float, default=0.4, help="章节之间的间隔秒数")
    args = ap.parse_args()

    sid = series_id_of(args.series)
    out_dir = os.path.abspath(args.out)
    img_dir = os.path.join(out_dir, "images")
    cover_dir = os.path.join(out_dir, "covers")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(cover_dir, exist_ok=True)

    series = series_meta(sid)
    log(f"系列：{series['title']} / {series['userName']} / "
        f"{series.get('publishedContentCount')} 话")

    # 系列封面：size 只有这几个合法，/img-original/ 会 404
    urls = series["cover"]["urls"]
    cover_url = next((urls[k] for k in ("1200x1200", "600x600", "480mw", "240mw")
                      if k in urls), list(urls.values())[-1])
    saved = download(cover_url, os.path.join(out_dir, "covers", "00_series_cover.jpg"))
    cover_file = os.path.relpath(saved, out_dir).replace(os.sep, "/") if saved else None
    if not saved:
        log("  ! 系列封面下载失败")

    eps = episodes(sid)
    log(f"章节：{len(eps)} 话")

    chapters, cache, missing = [], {}, []
    for ep in eps:
        body = getjson(f"{BASE}/ajax/novel/{ep['id']}")["body"]
        content = body.get("content") or ""
        saved = download(ep["cover_url"],
                         os.path.join(out_dir, "covers",
                                      f"{ep['order']:02d}_{slug(ep['title'], 40)}.jpg"))
        cover_local = os.path.relpath(saved, out_dir).replace(os.sep, "/") if saved else None
        if not saved:
            log(f"  ! 第{ep['order']}话封面下载失败")

        content_local = localize_content(content, out_dir, ep["order"],
                                         img_dir, cache, missing)
        chapters.append({
            **ep,
            "title": body.get("title") or ep["title"],
            "description": clean_description(body.get("description")),
            "character_count": body.get("characterCount", ep["text_count"]),
            "content": content_local,
            "raw_content": content,
            "cover": cover_local,
            "images": sorted({m.group(1) for m in IMG_TAG.finditer(content)}),
        })
        log(f"  [{ep['order']:02d}] {ep['title']}  {len(content)} 字  "
            f"{len(chapters[-1]['images'])} 图")
        time.sleep(args.delay)

    book = {
        "series": {
            "id": sid,
            "title": series["title"],
            "author": series["userName"],
            "author_id": series["userId"],
            "caption": clean_description(series.get("caption")),
            "url": f"{BASE}/novel/series/{sid}",
            "cover": cover_file,
            "cover_url": cover_url,
            "episode_count": len(chapters),
        },
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "chapters": chapters,
    }
    with open(os.path.join(out_dir, "book.json"), "w", encoding="utf-8") as f:
        json.dump(book, f, ensure_ascii=False, indent=1)

    total = sum(len(c["content"]) for c in chapters)
    log(f"完成：{out_dir}  正文约 {total} 字"
        + (f"，{len(missing)} 处图片失败：{missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
