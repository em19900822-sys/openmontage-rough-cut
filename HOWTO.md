# OpenMontage Rough Cut — HOWTO (this box)

Installed at: `/home/box/skills/openmontage-rough-cut`  
Upstream: https://github.com/em19900822-sys/openmontage-rough-cut  
Has `SKILL.md`: **yes** (Codex/agent skill for 中文口播粗剪)

## What it does

Fast **first rough cut** of talking-head (口播) clips:

1. Agent builds an EDL (edit decision list) that keeps unique speech and drops repeated takes / failed starts.
2. Renderer trims each segment and hard-cuts them into one MP4.
3. **No** subtitles, beauty, music, overlays, speed change, or fancy transitions.

Design rule from SKILL.md: **漏删优于误删** (prefer missing a cut over cutting unique content).

## Dependencies on this box

| Dep | Status |
|-----|--------|
| ffmpeg / ffprobe | ✅ system (`/usr/bin/ffmpeg` 7.1.x) |
| Python 3 | ✅ for Linux renderer |
| Windows PowerShell 7 + original `.ps1` | ❌ not installed (repo script is Windows-first) |
| OpenMontage desktop app | ❌ not installed — optional for project/transcript reuse; agent can build EDL from user transcript + timestamps |

**Use the Python renderer on this Linux box.** Prefer `--encoder libx264` (no Intel QSV GPU here).

## Key files

| Path | Role |
|------|------|
| `SKILL.md` | Agent workflow: delete rules, EDL schema, acceptance |
| `scripts/render_rough_cut.py` | **Linux renderer** (added on this box) |
| `scripts/render_rough_cut.ps1` | Upstream Windows renderer (PS5 读中文 UTF-8 EDL 会失败，Windows 上也优先用 .py) |
| `scripts/map_timeline.py` | 成片时间 → EDL 段/源片时间 + 附近切点（返修第一步） |
| `scripts/probe_window.py` | 源片窗口 50ms 音量曲线 + 静音区间；`--sheet` 出带时间标签的抽帧拼图 |
| `scripts/transcribe_words.py` | faster-whisper 逐词转录；`--no-vad` 重转可疑窗口 |
| `references/pipeline.md` | 飞书 lark-cli、跨机器搬文件、转录坑、Windows 渲染 |
| `references/revision-loop.md` | 客户返修流程、用户说法对照表、精修技术、报告模板 |
| `references/case-2026-10-25.md` | 10.25 四版返修实战案例 |
| `agents/openai.yaml` | Codex display name / default prompt |
| `tests/test_render_rough_cut.ps1` | Upstream PlanOnly contract test |

## EDL format (`rough-cut-v1`)

```json
{
  "version": "rough-cut-v1",
  "segments": [
    {
      "order": 1,
      "input_path": "/path/to/01.MOV",
      "start_seconds": 3.02,
      "end_seconds": 47.98,
      "reason": "保留完整开头，删除随后重复的一遍"
    }
  ]
}
```

Each segment needs: `order`, `input_path`, `start_seconds`, `end_seconds`, `reason`.

## Invoke — plan only (validate EDL, no render)

```bash
SKILL=/home/box/skills/openmontage-rough-cut
python3 "$SKILL/scripts/render_rough_cut.py" \
  --edl /path/to/rough_cut_v1_edl.json \
  --output /path/to/粗剪第一版.mp4 \
  --plan-only
```

Prints JSON with `segment_count`, `estimated_duration_seconds`, encoder candidates.

## Invoke — real rough cut

```bash
SKILL=/home/box/skills/openmontage-rough-cut
python3 "$SKILL/scripts/render_rough_cut.py" \
  --edl /path/to/rough_cut_v1_edl.json \
  --output /path/to/粗剪第一版.mp4 \
  --encoder libx264
```

On success prints JSON: `status=pass`, paths, duration check (±1s), codec info, `full_decode=pass`.

Help:

```bash
python3 /home/box/skills/openmontage-rough-cut/scripts/render_rough_cut.py --help
```

## Agent workflow (from SKILL.md)

1. Collect local talking-head clips (folder order or user-specified order). **Never overwrite sources.**
2. Get transcript: Feishu doc, user text, or local word-level timestamps. Prefer reuse; paid ASR only with user OK.
3. Build EDL: drop clear repeats / failed starts / countdown; keep unique points and natural fillers when unsure.
4. `--plan-only` first, then full render.
5. Deliver only to a **user-specified** output path; report duration, specs, and anything left uncertain.

## Smoke test results (this install)

- `--help` OK
- `--plan-only` with 2 dummy segments → `segment_count=2`, `estimated_duration_seconds=3.5` OK
- Tiny ffmpeg-generated clips → real render `status=pass`, duration 2.5s matches EDL OK

## Notes / gaps

- Upstream targets **Windows + OpenMontage**; this box runs the **Python port**.
- Transcription / Feishu / OpenMontage project files are **not** bundled — the bot must obtain timestamps (user paste, Whisper, etc.) before writing EDL.
- Default `auto` encoder tries `h264_qsv` then falls back to `libx264`; on this CPU box always pass `--encoder libx264` to skip a failed QSV attempt.

## 新增辅助脚本（2026-10-27）

只依赖 ffmpeg + Python 标准库（`probe_window.py` 的拼图标签可选 Pillow；`transcribe_words.py` 需 faster-whisper，放 venv）。Windows 用户电脑上同样可用。

```bash
S=/home/box/skills/openmontage-rough-cut/scripts
# 1) 返修第一步：把客户报的成片时间换算回源片，并列出 ±3s 内的切点
python3 $S/map_timeline.py --edl rough_cut_v3_edl.json --at 0:58 --at 3:10 --at 7:08 --window 3
# 2) 看某个窗口的音量曲线 / 静音区间（说话约 -30~-45 dB，静音约 -70 dB）
python3 $S/probe_window.py --media 3.MOV --start 88.9 --end 92.6
#    同时出 10fps 抽帧拼图（每格标源片秒数），用 Read 看图确认动作起止
python3 $S/probe_window.py --media 3.MOV --start 88.9 --end 92.6 --sheet i8.png
# 3) 词级转录；可疑区间关 VAD 重转
python3 $S/transcribe_words.py --wav 1.wav --out 1.json
python3 $S/transcribe_words.py --wav 4.wav --start 70 --end 106 --no-vad
```

自测（2026-10-27）：map_timeline 对 v3 EDL 换算 0:58/0:24/7:08 结果与人工一致；probe_window 在 3.wav 89.1–92.5 测出静音 89.30–92.25；合成视频拼图输出 10 格带标签；transcribe_words --no-vad 在 4.wav 86–103 正确识别出三遍重复。

## 2026-10-27 更新
按 skill-creator 原则重写 SKILL.md（触发描述、通用流程、第一版自检清单、Linux/Windows 渲染），把实战细节移到 references/。备份：`/home/box/skills/openmontage-rough-cut.bak-20261027/`。
