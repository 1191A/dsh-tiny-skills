# dsh-tiny-skills

[English](README.en.md) | 中文

一小把「小而美」的 agent skill。每个只解决一件具体的事，装进去就能用，不需要框架、不需要 API key、不需要先读三十页文档。

共同的三条原则：

- **脚本能单独跑。** 逻辑写在可执行的脚本里，SKILL.md 只负责讲什么时候用、为什么这么做，而不是把一堆步骤念一遍。
- **能不依赖就不依赖。** 优先 Python 标准库；确实需要外部工具时，在文档里写清楚缺了会怎样降级。
- **踩过的坑写进文档。** 接口的怪癖、平台的限制、为什么不能用某种显然的写法——这些才是技能真正的价值。

## 技能

| 技能 | 一句话 | 依赖 |
|---|---|---|
| [`explain-material`](#explain-material--把材料变成讲义) | 课件 / PDF / 视频 → 能直接读的讲义 | `python3`（渲染和转写可选装 `java`、`poppler-utils`、`ffmpeg`） |
| [`no-hint-recall`](#no-hint-recall--陪你把题重新推一遍) | 把「看懂了」练成「做得出」 | `python3` |
| [`pixiv-novel-archiver`](#pixiv-novel-archiver--pixiv-小说系列归档) | pixiv 小说系列 → 带插图的 EPUB | `python3`（纯标准库） |

---

### `explain-material` — 把材料变成讲义

丢一个 PPT / PDF / Word / 图片 / 视频进去，产出一份能直接读的 markdown 讲义：补上材料省略的推理、把公式按原页面转写、把配图放到相应段落旁边。

```bash
python3 skills/explain-material/scripts/ingest.py 课件.ppt
# → 课件_ingest/source.md + images/（ppt 会逐页渲染成 PNG）
```

它不是把页面切成小节罗列，而是按「问题 → 办法 → 推广 → 边界」重排。材料里那些"取同心球面""作辅助线连接 EF"式的跳步，会被补上"为什么要这么取"。

### `no-hint-recall` — 陪你把题重新推一遍

当你已经看过解析、却还是做不出来时用它。它不会讲题，它会**把答案按住**：先问卡在哪、一次只放一格提示、给完全解必须回讲。

配套产出是一张「还原卡」（五个问题 + 21 天复习节奏），把一次推导变成能重新启动的东西。

这两个技能都从同一个观察出发：**看懂和会做是两种能力**。前者靠识别，后者靠提取；材料组织和练习方式要分别对待。

### `pixiv-novel-archiver` — pixiv 小说系列归档

给一条 pixiv 小说系列链接，把每一话正文、正文里的插图原图、系列封面和各话封面全部存下来，打包成能直接丢进阅读器的 EPUB，外加 Markdown 和手机友好的网页。

```bash
python3 skills/pixiv-novel-archiver/scripts/pixiv_fetch.py \
  https://www.pixiv.net/novel/series/1280985 -o out
python3 skills/pixiv-novel-archiver/scripts/pixiv_build.py out --zip
```

pixiv 的小说页是前端渲染的，抓 HTML 拿不到正文，得走它自己的 JSON 接口。脚本里固化了这些细节：

- 章节列表接口的 `limit` 上限是 10，而且**不能**带 `lang` 参数（会 400）
- 章节是倒序返回的，落盘前必须按 `seriesContentOrder` 重排
- 图片必须带 `Referer: https://www.pixiv.net/`，否则 403
- 封面只有 `/c/` 缩略图可用，`/img-original/` 是 404
- 正文里 `[pixivimage:id-page]` 的页码从 1 起，原图文件名是 `_p0`，差一

EPUB 里系列封面作扉页，每话扉页放该话封面；同一张封面在连续几话重复出现时自动合并成「封面同前（第 N 话）」。

## 安装

```bash
git clone git@github.com:1191A/dsh-tiny-skills.git
cd dsh-tiny-skills
cp -r skills/* ~/.dsh/skills/          # DSH
# 或 cp -r skills/* ~/.claude/skills/  # Claude Code
```

技能目录格式遵循 SKILL.md + YAML frontmatter，两边通用。

## 依赖

按需安装，缺了会降级并在报告里说明，不会静默失败。

| 用途 | 依赖 |
|---|---|
| 基础（一切都靠它） | `python3` |
| `.ppt` 逐页渲染 | `java` + `bash skills/explain-material/scripts/poi/fetch.sh` |
| 中文正常显示 | 一套中文字体（如 `fonts-noto-cjk`） |
| PDF | `poppler-utils`（`pdftotext` / `pdftoppm`） |
| 视频抽帧、抽音轨 | `ffmpeg` |
| 本地语音转写 | `pip install faster-whisper` |
| `.docx` / `.xlsx` | 内置解析；xlsx 可选 `openpyxl` |

`scripts/poi/` 里不提交 jar（约 6MB），用 `fetch.sh` 拉取并编译。

## 举例：一次典型的处理

```
课件.ppt (123 页, 4.7MB)
  → ingest.py                    # 逐页渲染 123 张 PNG，每页文字对齐
  → 体检                         # 哪几页式子叠字读不到，先说清楚
  → 按节写讲义                    # 10 节，每节 800–1500 字
  → pack.py                      # 只复制讲义真正引用到的 41 张图
  → <workspace>/讲义/静电学/      # 目录.md + 10 份 md + images/
```

## 已知限制

- `.pptx` 目前只抽文字和媒体图，不渲染版面；需要渲染就先另存为 `.ppt`。
- 逐页渲染依赖原文件字体，缺字体会出现方框。
- Linux 容器里 LibreOffice 可能起不来（`/proc not mounted`），所以走的是 Apache POI + Java AWT 这条路。
- 内置视频工具的 ASR 需要 API key；没有就走本地 faster-whisper。
- 少数原文件的内容框重叠会导致式子读不出，此时讲义里会写明"读不到"，不猜。
- pixiv 抓取只支持公开作品，接口改了就得跟着改。

## License

MIT。`skills/explain-material/scripts/poi/` 使用 Apache POI（Apache License 2.0），jar 由 `fetch.sh` 单独获取，不随本仓库分发。
