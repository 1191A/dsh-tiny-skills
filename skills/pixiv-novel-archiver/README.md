# pixiv-novel-archiver

把 [pixiv](https://www.pixiv.net) 上一个小说系列完整存下来：每一话的正文、正文里引用的插图原图、系列封面与各话封面，最后打包成能直接读的 **EPUB**、网页和 Markdown。

pixiv 的小说页是前端渲染的，直接抓 HTML 拿不到正文。这个工具走 pixiv 自己的公开 JSON 接口，把接口细节、网络坑和排版成品都固化成了两个脚本 + 一份给 AI agent 用的技能说明。

```
$ python3 scripts/pixiv_fetch.py https://www.pixiv.net/novel/series/1280985 -o out
系列：ロストデリューション / 幸益アリス / 7 话
  [01] 桜の雪が降る季節  2579 字  1 图
  ...
$ python3 scripts/pixiv_build.py out --zip
```

## 特点

- **只要 Python 3，零依赖**，不需要 pip install，也不需要登录 pixiv
- **正文按原样保留**：换行、全角缩进、`[newpage]` 分页、`[chapter:]` 小节、注音标记都能还原
- **插图下原图**，不是缩略图；原图是 png 或被删了会自动回退
- **EPUB 可以直接导入手机阅读器**：系列封面作扉页、每话扉页放该话封面（重复的自动合并成「封面同前」）、目录、插图内嵌
- **另出 Markdown 和自适应的 HTML**，方便再加工或直接看
- 手机网络下也能跑：所有请求带重试与退避

## 用法

```bash
git clone git@github.com:1191A/pixiv-novel-archiver.git
cd pixiv-novel-archiver

# 1. 抓数据（系列 ID 或整条链接都行）
python3 scripts/pixiv_fetch.py 1280985 -o out

# 2. 生成成品
python3 scripts/pixiv_build.py out --zip
```

产物：

```
out/
├── book.json          # 结构化数据（正文里的图片已换成本地路径）
├── images/            # 正文插图原图
├── covers/            # 00_ 系列封面，其余各话封面
├── 01_<章节名>.md …   # 单章 Markdown
├── 全集.md
├── index.html
├── <书名>.epub
└── ../out.zip
```

`pixiv_build.py` 可以单独重跑，只重建想要的格式：

```bash
python3 scripts/pixiv_build.py out --no-epub     # 只出 md + html
python3 scripts/pixiv_build.py out --no-md --no-html
```

## 作为 AI 技能安装

本仓库同时是一个 [Claude Skill](https://docs.claude.com/en/docs/claude-code/skills)：`SKILL.md` 描述什么时候该用它、接口怎么调、哪些坑要绕开。放进你的技能目录即可：

```bash
git clone git@github.com:1191A/pixiv-novel-archiver.git ~/.dsh/skills/pixiv-novel-archiver
```

（Claude Code 用户放到 `~/.claude/skills/`，其它 agent 框架同理。）

## 接口备忘

| 用途 | 接口 |
|---|---|
| 系列信息 | `/ajax/novel/series/{series_id}` |
| 章节列表 | `/ajax/novel/series_content/{series_id}?last_order={n}&limit=10` |
| 单话正文 | `/ajax/novel/{novel_id}` |
| 插图原图 | `/ajax/illust/{illust_id}` → `urls.original` |

图片必须带 `Referer: https://www.pixiv.net/`，否则 403。`limit` 上限是 10，且不能加 `lang` 参数（会 400）。

## 已知限制

- 只支持公开作品；需要登录或已删除的系列会失败
- 不支持漫画、插画集（这是小说专用）
- pixiv 改接口就得跟着改，脚本里每个请求都集中在一处，好改
- 抓取频率别太猛，脚本默认每话间隔 0.4 秒

## 声明

仅供个人备份与阅读。请自行确认你有权保存对应内容，不要二次分发作者的作品。所有版权归原作者所有。

## License

MIT
