# dsh-study-skills

Two agent skills for students learning on their own. One turns source material into a readable handout; the other drills the gap between "I understood it" and "I can do it".

Both start from the same observation: **understanding and reproducing are different abilities.** The first runs on recognition, the second on retrieval. Material design and practice design have to treat them separately.

## Skills

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

## Install

```bash
git clone <repo> && cd dsh-study-skills
cp -r skills/* ~/.dsh/skills/          # DSH
# or cp -r skills/* ~/.claude/skills/  # Claude Code
```

Skills are plain `SKILL.md` + YAML frontmatter, so both hosts read them.

## Dependencies

Install only what you need. Missing pieces degrade gracefully and are reported, never silently ignored.

| Purpose | Requirement |
|---|---|
| Base (everything) | `python3` |
| `.ppt` page rendering | `java` + `bash skills/explain-material/scripts/poi/fetch.sh` |
| CJK text rendering | a CJK font (e.g. `fonts-noto-cjk`) |
| PDF | `poppler-utils` (`pdftotext` / `pdftoppm`) |
| Video frames, audio track | `ffmpeg` |
| Local speech-to-text | `pip install faster-whisper` |
| `.docx` / `.xlsx` | built in; `openpyxl` optional for xlsx |

Jars (~6 MB) are not committed; `fetch.sh` downloads and compiles them.

## A typical run

```
lecture.ppt (123 slides, 4.7 MB)
  → ingest.py            # 123 PNGs, text aligned per slide
  → triage               # flag pages whose formulas overlap and cannot be read
  → write per section    # 10 handouts, 800–1500 characters each
  → pack.py              # copy only the 41 figures actually referenced
  → output folder        # index.md + 10 handouts + images/
```

## Known limits

- `.pptx` is text + embedded media only; page layout is not rendered. Convert to `.ppt` first if you need rendering.
- Rendering depends on the fonts installed; missing fonts show as boxes.
- LibreOffice often fails inside a Linux container (`/proc not mounted`), which is why rendering goes through Apache POI + Java AWT instead.
- The built-in video tool's ASR needs an API key; without one, use local `faster-whisper`.
- Overlapping text frames in the original file can make a formula unreadable — handouts then say "cannot read this page" rather than guessing.

## License

MIT. `skills/explain-material/scripts/poi/` uses Apache POI (Apache License 2.0); its jars are fetched by `fetch.sh` and are not redistributed here.
