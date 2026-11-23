---
name: pixiv-novel-archiver
description: 抓取 pixiv 小说系列（pixiv小説 / ノベル）的全部正文、插图原图与封面，并打包成 Markdown / HTML / EPUB 供手机阅读。当用户给出 pixiv 小说链接或系列 ID，说「把这个小说抓下来」「下载 pixiv 小说系列」「做成 epub 放到手机上看」「插图和封面一起存」「备份 pixiv 小説」时使用；也用于排查这类抓取脚本的问题（图片 403、章节分页、封面重复、EPUB 打不开）。Use when the user wants to download or archive a pixiv novel series — text, illustrations, cover — or turn it into an EPUB.
---

# pixiv 小说系列归档

把 pixiv 上一个小说系列完整存下来：每话正文、正文里引用的插图原图、系列封面与各话封面，最后打包成能直接读的 EPUB 和网页。pixiv 的网页是前端渲染的，直接抓 HTML 拿不到正文，要走它自己的 JSON 接口——这个技能把接口细节、网络坑和排版成品都固化下来了。

## 快速开始

```bash
python3 scripts/pixiv_fetch.py https://www.pixiv.net/novel/series/1280985 -o out
python3 scripts/pixiv_build.py out --zip
```

第一条抓数据（写 `out/book.json`、`out/images/`、`out/covers/`），第二条生成成品。脚本只用 Python 标准库，不需要 pip 安装任何东西。

先跑 `fetch`，看一眼 `book.json` 里章节数和正文长度是否合理，再跑 `build`。抓取大约每话 1 张图，几十 MB 是正常的。

## 接口备忘录

全部是公开接口，**不需要登录**，但必须带浏览器 User-Agent，图片必须带 `Referer: https://www.pixiv.net/`，否则 403。

| 用途 | 接口 |
|---|---|
| 系列信息（标题/作者/封面/话数） | `/ajax/novel/series/{series_id}` |
| 章节列表（分页） | `/ajax/novel/series_content/{series_id}?last_order={n}&limit=10` |
| 单话正文 | `/ajax/novel/{novel_id}` |
| 插图原图地址 | `/ajax/illust/{illust_id}` 里的 `urls.original` |

正文在 `body.content`，是带标记的纯文本：

- `[pixivimage:12345678-2]` —— 引用某张插图的第 2 页（页码从 1 起，原图文件名是 `_p1`，注意差一）
- `[newpage]` —— 分页符
- `[chapter:标题]` —— 小节标题
- `[jump:N]` —— 跳转标记，丢掉
- `[[rb:汉字 > 假名]]` —— 注音，取汉字

## 踩过的坑

**`limit` 最大就是 10，而且不能加 `lang` 参数。** 加上 `?lang=zh` 直接 400，像是接口只认裸参数。翻页用返回里的 `page.nextPage` 判断，`last_order` 传上一页最后一话的 `seriesContentOrder`。

**章节是倒序返回的。** 接口按最新话在前给，落盘前按 `seriesContentOrder` 排一遍，否则整本书会从结尾读到开头。

**封面没有原图。** `novel-cover-master` 只有 `/c/` 缩略图，`/img-original/` 是 404。可用的尺寸是 `1200x1200`、`600x600`、`480x960`、`240x480_80`，优先取最大的那个。`/ajax/illust/{id}` 给出的 `urls.original` 只适用于插图。

**插图原图可能是 png。** `.jpg` 404 时换 `.png` 再试；原图被作者删掉的话，退回 `img-master` 的 `_master1200` 版本。脚本里 `download()` 已经把这条处理好了。

**手机网络会抽风。** TLS 握手经常 `UNEXPECTED_EOF_WHILE_READING`，所有请求都要重试（脚本里 5 次、递增退避）。抓 7 话大概会撞上一两次，别当成接口坏了。

**同一张封面会出现在好几话里。** 作者中途换过封面的话，pixiv 会给连续的几话返回同一张图，字节完全一致。这是真实数据，不是下载串了。EPUB 里对重复封面做了去重：第一次出现贴图，后面标「封面同前（第 N 话）」，否则连着两页一模一样很怪。

## 成品长什么样

```
out/
├── book.json                 # 结构化数据，content 里的图片已换成本地路径
├── images/                   # 正文插图原图，文件名带话号与 illust id
├── covers/                   # 00_ 是系列封面，其余是各话封面
├── 01_<章节名>.md …          # 单章，标题下是该话封面
├── 全集.md                   # 全部章节合成一本
├── index.html                # 手机浏览器阅读页（深色模式自适应）
└── <书名>.epub               # 系列封面作扉页 + 各话封面 + 插图 + 目录
```

EPUB 有几个必须对的细节，脚本已经处理：`mimetype` 必须是压缩包里第一个条目且不压缩；`content.opf` 里声明 `cover-image`；`nav.xhtml` 和 `toc.ncx` 都要有，老阅读器只认 ncx。

## 交付时

把 EPUB 和压缩包放到用户能看到的位置（本机是 `/sdcard/Download/DSH-Go/`），并在回复里说清楚：抓了几话、多少字、几张插图、文件多大。如果某张图失败，明确告诉用户是哪一张，别默默吞掉——`book.json` 里对应位置会留一行「（插图 xxx 下载失败）」。

只处理用户有权保存的内容，抓下来的东西别二次分发。这是给个人阅读和备份用的工具。
