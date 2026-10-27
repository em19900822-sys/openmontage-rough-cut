#!/usr/bin/env python3
"""检查源片某个时间窗：50ms 音量曲线 + 静音区间，可选输出带时间标签的抽帧拼图。

用法:
  # 音量曲线（可直接对 .MOV 或抽出的 wav）
  python probe_window.py --media 3.MOV --start 88.9 --end 92.6
  # 同时出拼图（每 0.1s 一帧，10 列）；装了 Pillow 会在每格左上角标源片时间
  python probe_window.py --media 3.MOV --start 88.9 --end 92.6 --sheet i8.png [--fps 10] [--cols 10]

判读：说话约 -30~-45 dB，静音约 -70 dB（阈值随录音环境略变，先看本片的底噪）。
只依赖 ffmpeg 与 Python 标准库；Pillow 可选。
"""
import argparse, array, math, shutil, subprocess, sys


def energy(media, start, end, step, thr):
    sr = 16000
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start}", "-to", f"{end}", "-i", media,
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    x = array.array("h"); x.frombytes(raw[: len(raw) // 2 * 2])
    n = int(step * sr)
    rows, sil, cur = [], [], None
    for i in range(0, len(x), n):
        blk = x[i:i + n]
        if not blk:
            break
        rms = math.sqrt(sum(v * v for v in blk) / len(blk)) / 32768
        db = 20 * math.log10(rms + 1e-9)
        t = start + i / sr
        rows.append((t, db))
        if db < thr:
            cur = cur if cur is not None else t
        elif cur is not None:
            sil.append((cur, t)); cur = None
    if cur is not None:
        sil.append((cur, start + len(x) / sr))
    return rows, sil


def sheet(media, start, end, out, fps, cols, width):
    nframes = max(1, math.ceil((end - start) * fps))
    rows = math.ceil(nframes / cols)
    vf = f"fps={fps},scale={width}:-2,tile={cols}x{rows}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-t", f"{end - start}", "-i", media,
                    "-vf", vf, "-frames:v", "1", out], check=True)
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print(f"拼图: {out}（未装 Pillow，无标签；第 k 格 = {start} + k/{fps} 秒，从左到右、从上到下）")
        return
    im = Image.open(out).convert("RGB"); d = ImageDraw.Draw(im)
    cw = im.size[0] // cols; ch = im.size[1] // rows
    for k in range(nframes):
        r, c = divmod(k, cols)
        d.rectangle([c * cw, r * ch, c * cw + 56, r * ch + 14], fill="black")
        d.text((c * cw + 2, r * ch + 1), f"{start + k / fps:.2f}", fill="yellow")
    im.save(out)
    print(f"拼图: {out}（{nframes} 格，每格标源片秒数）")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--media", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--silence-db", type=float, default=-60.0, help="低于此值算静音 (默认 -60)")
    ap.add_argument("--sheet", help="输出拼图 png 路径")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--width", type=int, default=160)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    rows, sil = energy(a.media, a.start, a.end, a.step, a.silence_db)
    print(f"音量曲线 {a.media} {a.start}-{a.end}s（每 {a.step}s, dBFS）")
    for i in range(0, len(rows), 10):
        print("  " + " ".join(f"{t:.2f}:{db:.0f}" for t, db in rows[i:i + 10]))
    print("静音区间(<%.0f dB):" % a.silence_db, ", ".join(f"{s:.2f}-{e:.2f} ({e - s:.2f}s)" for s, e in sil) or "无")
    if a.sheet:
        sheet(a.media, a.start, a.end, a.sheet, a.fps, a.cols, a.width)


if __name__ == "__main__":
    main()
