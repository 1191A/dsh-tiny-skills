#!/usr/bin/env python3
"""pack — 把一份讲义 md 和它引用的图，打包到交付目录。

用法:
    python3 pack.py <讲义.md> <抽图目录> <交付目录>

只复制讲义里真正引用到的图片，不会把上百张幻灯片全打包。
"""
import re
import shutil
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 4:
        sys.exit("用法: pack.py <讲义.md> <抽图目录> <交付目录>")
    md_path, imgdir, dest = (Path(x).expanduser() for x in sys.argv[1:4])

    if not md_path.exists():
        sys.exit("找不到讲义: %s" % md_path)
    text = md_path.read_text(encoding="utf-8")
    refs = sorted(set(re.findall(r"!\[[^\]]*\]\((images/[^)]+)\)", text)))

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "images").mkdir(exist_ok=True)
    shutil.copy2(md_path, dest / md_path.name)

    missing, copied = [], 0
    for ref in refs:
        src = imgdir / Path(ref).name
        if src.exists():
            shutil.copy2(src, dest / "images" / src.name)
            copied += 1
        else:
            missing.append(ref)

    print("交付目录: %s" % dest)
    print("讲义: %s（引用 %d 张图，复制 %d 张）" % (md_path.name, len(refs), copied))
    if missing:
        print("⚠️ 找不到的图: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
