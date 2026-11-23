# dsh-tiny-skills

English | [中文](README.md)

A handful of small, self-contained agent skills. Each one solves exactly one thing, installs with a `cp`, and needs no framework, no API key, and no thirty pages of reading first.

Three shared principles:

- **The scripts run on their own.** The logic lives in executable scripts; `SKILL.md` explains *when* to use them and *why* they work that way, instead of narrating steps.
- **No dependencies unless truly needed.** Python standard library first. When an external tool is unavoidable, the docs say what happens without it.
- **Write down the traps.** API quirks, platform limits, and why the obvious approach does not work are the real value of a skill.

## Skills

| Skill | What it does | Deps |
|---|---|---|
| [`explain-material`](#explain-material--turn-material-into-a-handout) | lecture slides / PDF / video → a handout you can actually read | `python3` (optionally `java`, `poppler-utils`, `ffmpeg`) |
| [`no-hint-recall`](#no-hint-recall--re-derive-the-problem-yourself) | drills the gap between "I understood it" and "I can do it" | `python3` |
| [`pixiv-novel-archiver`](#pixiv-novel-archiver--archive-a-pixiv-novel-series) | pixiv novel series → EPUB with illustrations | `python3` (stdlib only) |

---

### `explain-material` — turn material into a handout

Drop in a PPT / PDF / Word file / image / video; get back a markdown handout you can actually read: gaps in the original reasoning filled in, formulas transcribed from the actual pages, figures placed next to the paragraph that discusses them.

```bash
python3 skills/explain-material/scripts/ingest.py lecture.ppt
# → lecture_ingest/source.md + images/ (each .ppt slide rendered to PNG)
```

It does not chop the deck into one section per slide. It reorganises along "problem → method → generalisation → limits". Those famous leaps — "take a concentric spherical Gaussian surface", "draw the auxiliary line EF" — get the missing *why* written back in.

### `no-hint-recall` — re-derive the problem yourself

For the case where you have already read the solution and still cannot reproduce it. It will not lecture you. It **holds the answer back**: asks where you got stuck, releases one rung of hint at a time, and if you demand the full solution you have to explain it back afterwards.

It also produces a "recall card" (five questions plus a 21-day review schedule) so one derivation becomes something you can restart later.

Both start from the same observation: **understanding and reproducing are different abilities.** The first runs on recognition, the second on retrieval.

### `pixiv-novel-archiver` — archive a pixiv novel series

Give it a pixiv novel series URL; it saves every chapter's text, the illustrations referenced in the text at full resolution, the series cover and each chapter's cover — then packages the lot into an EPUB you can drop straight into a phone reader, plus Markdown and a mobile-friendly HTML page.

```bash
python3 skills/pixiv-novel-archiver/scripts/pixiv_fetch.py \
  https://www.pixiv.net/novel/series/1280985 -o out
python3 skills/pixiv-novel-archiver/scripts/pixiv_build.py out --zip
```

pixiv renders novel pages client-side, so scraping the HTML gets you nothing — the scripts talk to pixiv's own JSON endpoints. Traps baked in:

- the chapter-list endpoint caps `limit` at 10 and **breaks on a `lang` parameter** (400)
- chapters come back newest-first; they must be re-sorted by `seriesContentOrder`
- images need `Referer: https://www.pixiv.net/` or they 403
- covers only exist as `/c/` thumbnails; `/img-original/` is a 404
- `[pixivimage:id-page]` pages are 1-based while the original files are `_p0`

In the EPUB the series cover becomes the frontispiece, each chapter gets its own cover page, and a cover that repeats across consecutive chapters is collapsed into "封面同前（第 N 话）".

## Install

```bash
git clone git@github.com:1191A/dsh-tiny-skills.git
cd dsh-tiny-skills
cp -r skills/* ~/.dsh/skills/          # DSH
# or cp -r skills/* ~/.claude/skills/  # Claude Code
```

Each skill is a directory with `SKILL.md` + YAML frontmatter, which both formats accept.

## Dependencies

Install on demand. Missing pieces degrade gracefully and are reported, never silently skipped.

| Purpose | Dependency |
|---|---|
| Base (everything needs it) | `python3` |
| `.ppt` slide rendering | `java` + `bash skills/explain-material/scripts/poi/fetch.sh` |
| CJK text | a CJK font (e.g. `fonts-noto-cjk`) |
| PDF | `poppler-utils` (`pdftotext`, `pdftoppm`) |
| Video frames / audio | `ffmpeg` |
| Local ASR | `pip install faster-whisper` |
| `.docx` / `.xlsx` | built in; optional `openpyxl` for xlsx |

No jars are committed under `scripts/poi/` (about 6MB); `fetch.sh` pulls and builds them.

## Known limits

- `.pptx` yields text and media only, no layout; convert to `.ppt` if you need rendering.
- Slide rendering depends on the source fonts — missing fonts become boxes.
- LibreOffice often fails to start in containers (`/proc not mounted`), hence the Apache POI + Java AWT route.
- The video tool's ASR needs an API key; without one it falls back to local faster-whisper.
- Overlapping text boxes occasionally make formulas unreadable; the handout says so instead of guessing.
- pixiv archiving works on public works only, and will need updating if pixiv changes its endpoints.

## License

MIT. `skills/explain-material/scripts/poi/` uses Apache POI (Apache License 2.0); the jars are fetched by `fetch.sh` and not redistributed here.
