"""Generate the narration audio for the KT video with Kokoro (runs locally).

Reads the **Narration** block of each scene in script.md and writes:
  audio/scene_XX.wav   one 24 kHz WAV per scene
  timing.json          scene durations (audio + padding + optional hold) with sentence and word timestamps
  captions.srt         sentence-level captions built from the same timestamps

Usage: .venv/Scripts/python.exe tts.py [--scenes 3,5] [--all]
By default only scenes whose narration changed (or whose WAV is missing) are regenerated.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "script.md"
AUDIO = HERE / "audio"
TIMING = HERE / "timing.json"
SRT = HERE / "captions.srt"
VOICE = "af_heart"
RATE = 24000
PADDING = 0.6
SENTENCE_SPLIT = r"(?<=[.!?:])\s+"


def read_scenes() -> list[dict]:
    text = SCRIPT.read_text(encoding="utf-8")
    scenes = []
    for block in re.split(r"^## Scene ", text, flags=re.M)[1:]:
        header = block.splitlines()[0]
        number = int(header.split()[0])
        title = header.split("—", 1)[1].split("(")[0].strip()
        chapter = re.search(r'chapter "([^"]+)"', header).group(1)
        narration = re.search(r"\*\*Narration\*\*\s*\n(.*?)\n\s*\*\*On screen", block, re.S).group(1)
        hold = re.search(r"hold ([\d.]+)", header)  # optional extra seconds, e.g. for an end card
        scenes.append({"scene": number, "title": title, "chapter": chapter,
                       "narration": " ".join(narration.split()), "hold": float(hold.group(1)) if hold else 0.0})
    return scenes


def synthesize(pipeline, text: str):
    """Return (audio, sentences, words) with times in seconds from the start of the scene."""
    chunks, sentences, words = [], [], []
    offset = 0.0
    for result in pipeline(text, voice=VOICE, speed=1, split_pattern=SENTENCE_SPLIT):
        audio = result.audio.numpy() if hasattr(result.audio, "numpy") else np.asarray(result.audio)
        length = len(audio) / RATE
        sentences.append({"text": result.graphemes.strip(), "start": round(offset, 3),
                          "end": round(offset + length, 3)})
        for tok in result.tokens or []:
            if tok.start_ts is None or not tok.text.strip() or not re.search(r"\w", tok.text):
                continue
            words.append({"word": tok.text, "start": round(offset + tok.start_ts, 3),
                          "end": round(offset + (tok.end_ts or tok.start_ts), 3)})
        chunks.append(audio)
        offset += length
    return np.concatenate(chunks), sentences, words


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def caption_text(text: str) -> str:
    """Undo the pronunciation respellings so captions read naturally."""
    for spoken, written in [("F-A-Q", "FAQ"), ("Jason", "JSON"), ("Lite L-L-M", "LiteLLM"), ("L-L-M", "LLM"),
                            ("pie-test", "pytest"), ("Pie-dantic", "Pydantic"), ("pie-dantic", "Pydantic"),
                            ("P-R-D", "PRD"), ("Ahsha's", "Asha's"), ("konfig", "config"),
                            ("back ends", "backends"), ("ee-val", "eval"), ("hours dot T-X-T, colon twelve", "hours.txt:12")]:
        text = text.replace(spoken, written)
    return text


def write_srt(timing: dict) -> None:
    lines, n, start = [], 1, 0.0
    for scene in timing["scenes"]:
        for s in scene["sentences"]:
            lines += [str(n), f"{srt_time(start + s['start'])} --> {srt_time(start + s['end'])}",
                      caption_text(s["text"]), ""]
            n += 1
        start += scene["duration"]
    SRT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", help="comma-separated scene numbers to regenerate (default: changed scenes)")
    parser.add_argument("--all", action="store_true", help="regenerate every scene")
    args = parser.parse_args()
    only = {int(s) for s in args.scenes.split(",")} if args.scenes else None

    from kokoro import KPipeline
    pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    AUDIO.mkdir(exist_ok=True)

    old = {s["scene"]: s for s in json.loads(TIMING.read_text())["scenes"]} if TIMING.exists() else {}
    scenes_out = []
    for scene in read_scenes():
        wav = AUDIO / f"scene_{scene['scene']:02d}.wav"
        prev = old.get(scene["scene"])
        changed = prev is None or prev.get("narration") != scene["narration"] or not wav.exists()
        if (only is None and changed) or (only is not None and scene["scene"] in only) or args.all:
            audio, sentences, words = synthesize(pipeline, scene["narration"])
            sf.write(wav, audio, RATE)
            entry = {**scene, "audio": wav.name, "audio_seconds": round(len(audio) / RATE, 3),
                     "sentences": sentences, "words": words}
            print(f"scene {scene['scene']}: {entry['audio_seconds']:.2f}s")
        else:
            entry = {**old[scene["scene"]], **scene}
        entry["duration"] = round(entry["audio_seconds"] + PADDING + entry["hold"], 3)
        scenes_out.append(entry)

    t = 0.0
    for s in scenes_out:
        s["start"] = round(t, 3)
        t += s["duration"]
    timing = {"fps": 30, "padding": PADDING, "sample_rate": RATE, "total": round(t, 3), "scenes": scenes_out}
    TIMING.write_text(json.dumps(timing, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_srt(timing)
    print(f"total {t:.2f}s")


if __name__ == "__main__":
    main()
