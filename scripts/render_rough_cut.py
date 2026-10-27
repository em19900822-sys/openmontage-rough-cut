#!/usr/bin/env python3
"""Linux/macOS port of render_rough_cut.ps1 — trim+concat from rough-cut EDL via ffmpeg."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def fmt_num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def load_edl(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = sorted(data.get("segments") or [], key=lambda s: int(s["order"]))
    if not segments:
        die("EDL contains no segments.")
    seen: set[int] = set()
    duration = 0.0
    for seg in segments:
        order = int(seg["order"])
        if order in seen:
            die(f"Duplicate segment order: {order}")
        seen.add(order)
        if not seg.get("input_path"):
            die(f"Segment {order} has no input_path.")
        src = Path(seg["input_path"])
        if not src.is_file():
            die(f"Segment source not found: {src}")
        start = float(seg["start_seconds"])
        end = float(seg["end_seconds"])
        if start < 0 or end <= start:
            die(f"Invalid range for segment {order}: {start}-{end}")
        duration += end - start
        seg["_start"] = start
        seg["_end"] = end
        seg["_src"] = src.resolve()
    return segments, duration


def build_filter(segments: list[dict], source_paths: list[Path]) -> str:
    parts: list[str] = []
    concat_inputs: list[str] = []
    for i, seg in enumerate(segments):
        idx = source_paths.index(seg["_src"])
        start = fmt_num(seg["_start"])
        end = fmt_num(seg["_end"])
        parts.append(f"[{idx}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[{idx}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs.append(f"[v{i}][a{i}]")
    return ";".join(parts) + ";" + "".join(concat_inputs) + f"concat=n={len(segments)}:v=1:a=1[v][a]"


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def main() -> None:
    ap = argparse.ArgumentParser(description="OpenMontage rough-cut renderer (EDL → mp4)")
    ap.add_argument("--edl", required=True, help="Path to rough_cut EDL JSON")
    ap.add_argument("--output", required=True, help="Output mp4 path")
    ap.add_argument(
        "--encoder",
        choices=("auto", "h264_qsv", "libx264"),
        default="auto",
        help="Video encoder (auto prefers QSV then libx264)",
    )
    ap.add_argument("--plan-only", action="store_true", help="Validate EDL and print plan JSON")
    args = ap.parse_args()

    edl_path = Path(args.edl).resolve()
    if not edl_path.is_file():
        die(f"EDL not found: {edl_path}")

    segments, duration = load_edl(edl_path)
    output_path = Path(args.output).resolve()

    if args.encoder == "h264_qsv":
        encoder_candidates = ["h264_qsv"]
    elif args.encoder == "libx264":
        encoder_candidates = ["libx264"]
    else:
        encoder_candidates = ["h264_qsv", "libx264"]

    plan = {
        "edl_path": str(edl_path),
        "output_path": str(output_path),
        "segment_count": len(segments),
        "estimated_duration_seconds": round(duration, 3),
        "video_encoder_candidates": encoder_candidates,
        "subtitles": False,
        "beauty": False,
        "transition": "hard_cut",
    }
    if args.plan_only:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    if not shutil.which("ffmpeg"):
        die("ffmpeg is unavailable.")
    if not shutil.which("ffprobe"):
        die("ffprobe is unavailable.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_paths: list[Path] = []
    for seg in segments:
        if seg["_src"] not in source_paths:
            source_paths.append(seg["_src"])

    base_args = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y"]
    for src in source_paths:
        base_args += ["-i", str(src)]

    filt = build_filter(segments, source_paths)
    used_encoder = None
    last_code = 1

    for candidate in encoder_candidates:
        if output_path.exists():
            output_path.unlink()
        cmd = base_args + ["-filter_complex", filt, "-map", "[v]", "-map", "[a]"]
        if candidate == "h264_qsv":
            cmd += [
                "-c:v", "h264_qsv", "-preset", "veryfast",
                "-global_quality", "22", "-look_ahead", "0", "-profile:v", "high",
            ]
        else:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high"]
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(output_path)]
        last_code = run(cmd)
        if last_code == 0 and output_path.is_file():
            used_encoder = candidate
            break

    if not used_encoder:
        die(f"Render failed with exit code {last_code}.")

    probe_raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of", "json", "--", str(output_path),
        ],
        text=True,
    )
    probe = json.loads(probe_raw)
    streams = probe.get("streams") or []
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(video) != 1 or len(audio) != 1:
        die("Output must contain one video stream and one audio stream.")

    decode_code = run(
        ["ffmpeg", "-v", "error", "-i", str(output_path), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", os.devnull]
    )
    if decode_code != 0:
        die("Full decode verification failed.")

    actual = float(probe["format"]["duration"])
    if abs(actual - duration) > 1.0:
        die(f"Output duration mismatch. Expected about {duration} seconds, got {actual}.")

    result = {
        "status": "pass",
        "output_path": str(output_path),
        "segment_count": len(segments),
        "expected_duration_seconds": round(duration, 3),
        "actual_duration_seconds": round(actual, 3),
        "size_bytes": int(probe["format"]["size"]),
        "video_encoder": used_encoder,
        "video_codec": video[0].get("codec_name"),
        "width": video[0].get("width"),
        "height": video[0].get("height"),
        "fps": video[0].get("r_frame_rate"),
        "audio_codec": audio[0].get("codec_name"),
        "sample_rate": audio[0].get("sample_rate"),
        "channels": audio[0].get("channels"),
        "full_decode": "pass",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
