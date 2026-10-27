#!/usr/bin/env python3
"""faster-whisper 词级转录（中文口播），可整段或只重转一个窗口。

  # 整段（16k 单声道 wav，先用 ffmpeg -vn -ac 1 -ar 16000 抽出）
  python transcribe_words.py --wav 1.wav --out 1.json
  # 可疑区间不开 VAD 重转（VAD 会吞掉重复句/轻声句）
  python transcribe_words.py --wav 4.wav --start 70 --end 106 --no-vad

依赖：pip install faster-whisper（建议放 venv）。直接用 wave 读 wav 成 numpy 数组，
绕开新版 PyAV 与 faster-whisper 1.2.x 的 `metadata_errors` 不兼容问题。
"""
import argparse, json, wave
import numpy as np


def load(path, start=None, end=None):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and sr == 16000, "需要 16k 单声道 16bit wav"
        if start:
            w.setpos(int(start * sr))
        n = w.getnframes() - w.tell() if end is None else int((end - (start or 0)) * sr)
        raw = w.readframes(n)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument("--model", default="small")
    ap.add_argument("--no-vad", action="store_true")
    ap.add_argument("--prompt", help="initial_prompt，可放规范稿里该处原句帮助识别")
    ap.add_argument("--out", help="输出 json；不给则只打印")
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    off = a.start or 0.0
    audio = load(a.wav, a.start, a.end)
    m = WhisperModel(a.model, device="cpu", compute_type="int8")
    segs, info = m.transcribe(audio, language="zh", word_timestamps=True, vad_filter=not a.no_vad,
                              condition_on_previous_text=False, initial_prompt=a.prompt)
    out = []
    for s in segs:
        words = [{"word": w.word, "start": round(w.start + off, 3), "end": round(w.end + off, 3)} for w in (s.words or [])]
        out.append({"start": round(s.start + off, 3), "end": round(s.end + off, 3), "text": s.text.strip(), "words": words})
        print(f"[{s.start + off:.2f}-{s.end + off:.2f}] {s.text.strip()}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"file": a.wav, "language": "zh", "duration": info.duration, "offset": off,
                       "vad": not a.no_vad, "segments": out}, f, ensure_ascii=False, indent=2)
        txt = a.out.rsplit(".", 1)[0] + ".txt"
        with open(txt, "w", encoding="utf-8") as f:
            for s in out:
                f.write(f"[{s['start']:.2f}-{s['end']:.2f}] {s['text']}\n")


if __name__ == "__main__":
    main()
