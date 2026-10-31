# Walkthrough video

A narrated walkthrough of this repo (about 5 minutes 20 seconds), with everything needed to re-render it.

| File | What it is |
|---|---|
| `kt-video.mp4` | The rendered video |
| `captions.vtt`, `chapters.txt`, `poster.jpg` | Captions, YouTube-style chapters, preview image |
| `outline.md` | Scene plan |
| `script.md` | Narration, on-screen beats and a source reference for every claim |
| `tts.py` | Local text-to-speech (Kokoro, voice `af_heart`) → `audio/scene_XX.wav`, `timing.json`, `captions.srt` |
| `timing.json` | Scene durations (whole frames) plus sentence and word timestamps |
| `composition.html` | All scenes as one 1920×1080 page; `window.renderAt(t)` draws the frame for time `t` |
| `render.mjs` | Renders each scene with Playwright into a cached segment, joins them, muxes audio with ffmpeg |

## Requirements

- Python 3.10–3.12 venv in `.venv` with `kokoro>=0.9` and `soundfile`; `espeak-ng` on the PATH
- Node 18+ (`npm install` in this folder installs Playwright), and `ffmpeg`/`ffprobe` on the PATH
- The fonts Bahnschrift, Segoe UI and Consolas (bundled with Windows)

## Render

```bash
cd docs/kt-video
npm install
npm run kt-video      # narration (changed scenes only) → changed scene segments → mp4
```

Outputs go to `out/` (`kt-video.mp4`, `captions.srt`, `chapters.txt`), and the video, captions, chapters and poster are
copied next to this README. A full render takes about 25 minutes; after that, only scenes that changed are rendered
again. Each scene's segment in `out/segments/` is named by a hash of its scene function, its timing, the shared page
code and styles, and the source files and screenshots the page shows. `node render.mjs --force` re-renders everything.

## Edit a scene

1. Change the scene's **Narration** in `script.md`. Spell out words the voice might mispronounce; `tts.py`
   (`caption_text`) maps the respellings back to normal spelling for the captions.
2. Run `.venv/Scripts/python.exe tts.py`. Only scenes whose narration changed are regenerated (`--scenes 3` forces
   one scene, `--all` forces every scene). Add `hold N` to a scene heading to keep it on screen N seconds longer.
3. Adjust the visuals in `composition.html`. Each scene is one function in `SCENES`; beats are tied to spoken words
   with `W(scene, "phrase")`, so they follow the audio when its timing changes. The render stops if a phrase is no
   longer in the narration.
4. Preview: `npm run preview`, then open the printed URL and use the scrub bar (Play uses `out/narration.wav`
   from the last render). Check single frames with `node render.mjs --frames 12.5,40`.
5. `npm run kt-video`.

Code excerpts are read from the real source files at render time, so line ranges in `composition.html` must be
updated if those files change.
