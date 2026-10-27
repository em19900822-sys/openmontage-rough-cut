#!/usr/bin/env python3
"""把成片时间点换算回 EDL 段和源片时间，并列出附近切点。

用法:
  python map_timeline.py --edl rough_cut_v3_edl.json --at 0:58 --at 3:10 [--window 3]
时间格式: 秒(58.2) / 分:秒(3:10.5) / 时:分:秒。只依赖标准库。
"""
import argparse, json, sys
from pathlib import Path


def parse_t(s: str) -> float:
    parts = [float(p) for p in s.split(":")]
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v


def fmt(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True)
    ap.add_argument("--at", action="append", required=True, help="成片时间，可重复")
    ap.add_argument("--window", type=float, default=3.0, help="在 ±window 秒内找切点 (默认 3)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
    segs = sorted(edl["segments"], key=lambda s: int(s["order"]))
    tl, t = [], 0.0
    for s in segs:
        d = float(s["end_seconds"]) - float(s["start_seconds"])
        tl.append((t, t + d, s))
        t += d
    total = t
    cuts = [(o1, i) for i, (o0, o1, s) in enumerate(tl[:-1])]  # 切点 = 第 i 段结束/第 i+1 段开始
    results = []
    for raw in a.at:
        x = parse_t(raw)
        hit = next(((o0, o1, s) for o0, o1, s in tl if o0 <= x < o1), tl[-1])
        o0, o1, s = hit
        src = float(s["start_seconds"]) + (x - o0)
        near = []
        for c, i in cuts:
            if abs(c - x) <= a.window:
                prev, nxt = tl[i][2], tl[i + 1][2]
                near.append({
                    "cut_out": round(c, 3), "cut_out_fmt": fmt(c), "delta": round(c - x, 2),
                    "prev": {"order": prev["order"], "input": Path(prev["input_path"].replace("\\", "/")).name, "end": prev["end_seconds"]},
                    "next": {"order": nxt["order"], "input": Path(nxt["input_path"].replace("\\", "/")).name, "start": nxt["start_seconds"]},
                })
        r = {"at": raw, "out_seconds": round(x, 3), "segment": s["order"],
             "input": Path(s["input_path"].replace("\\", "/")).name,
             "source_seconds": round(src, 3), "segment_out_range": [round(o0, 3), round(o1, 3)],
             "segment_src_range": [s["start_seconds"], s["end_seconds"]], "cuts_within_window": near}
        results.append(r)
    if a.json:
        print(json.dumps({"total_seconds": round(total, 3), "points": results}, ensure_ascii=False, indent=2))
        return
    print(f"EDL 总长 {total:.2f}s ({fmt(total)}), {len(segs)} 段")
    for r in results:
        print(f"\n[{r['at']}] 成片 {r['out_seconds']}s → 第{r['segment']}段 {r['input']} 源 {r['source_seconds']}s "
              f"(段: 成片 {fmt(r['segment_out_range'][0])}–{fmt(r['segment_out_range'][1])}, 源 {r['segment_src_range'][0]}–{r['segment_src_range'][1]})")
        if not r["cuts_within_window"]:
            print(f"  ±{a.window}s 内没有切点 → 问题在连续口播内部（停顿/动作/重复），或用户时间偏差更大")
        for c in r["cuts_within_window"]:
            print(f"  切点 {c['cut_out_fmt']} (差 {c['delta']:+.2f}s): 第{c['prev']['order']}段 {c['prev']['input']} 出点 {c['prev']['end']} | "
                  f"第{c['next']['order']}段 {c['next']['input']} 入点 {c['next']['start']}")


if __name__ == "__main__":
    sys.exit(main())
