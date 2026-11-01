# dsh-study-skills

[English](README.en.md) | 中文

两个给「学生自学」用的 DSH / Claude 技能。一个负责把材料变成讲义，一个负责把"看懂了"练成"做得出"。

它们的共同出发点很朴素：**看懂和会做是两种能力**。前者靠识别，后者靠提取；材料组织和练习方式要分别对待。

## 技能

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

## 安装

```bash
git clone <repo> && cd dsh-study-skills
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
  → /sdcard/Download/.../讲义/    # 目录.md + 10 份 md + images/
```

## 已知限制

- `.pptx` 目前只抽文字和媒体图，不渲染版面；需要渲染就先另存为 `.ppt`。
- 逐页渲染依赖原文件字体，缺字体会出现方框。
- Linux 容器里 LibreOffice 可能起不来（`/proc not mounted`），所以走的是 Apache POI + Java AWT 这条路。
- 内置视频工具的 ASR 需要 API key；没有就走本地 faster-whisper。
- 少数原文件的内容框重叠会导致式子读不出，此时讲义里会写明"读不到"，不猜。

## License

MIT。`skills/explain-material/scripts/poi/` 使用 Apache POI（Apache License 2.0），jar 由 `fetch.sh` 单独获取，不随本仓库分发。
