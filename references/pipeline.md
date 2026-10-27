# 输入、转录与渲染管线（实战踩坑）

## 目录
1. 飞书逐字稿
2. 素材在用户 Windows 电脑上
3. 转录（faster-whisper）
4. Windows 渲染
5. 验收

## 1. 飞书逐字稿
- 首选飞书 MCP / 连接器；用户授权不了（扫码卡片反复失败）时，改用共享电脑上已登录的 `lark-cli`：`lark-cli docs +fetch <wiki/doc 链接>`，把正文存成 `script_feishu.md`。
- 飞书稿是“规范稿/精修稿”，与真实口播有出入（多一句、少一句、换说法）。它只用来对齐和判断“这两句是不是重复”：规范稿里两句都有，就不是重复。剪辑依据永远是真实口播的时间戳。

## 2. 素材在用户 Windows 电脑上
- 原片 MOV 常一段 150–250MB，不要整段拷到共享电脑。只在用户电脑上用 ffmpeg 抽音轨过来转录：
  `ffmpeg -i 1.MOV -vn -ac 1 -ar 16000 -c:a pcm_s16le 1.wav`（每段约 5–8MB）。
- **CopyToBox / CopyFromBox 对 `D:\...` 等非用户目录路径可能被拒**：先把文件放到 `C:\Users\<用户>\Documents\<任务名>\` 中转，再拷。
- 用户电脑上的 PowerShell 默认是 Windows PowerShell 5：命令里不要混 bash 语法（如 `machineId=...`、`\$` 转义）；中文路径输出可能乱码，但用 `-LiteralPath` 访问是正常的。
- 工作区约定：EDL、脚本、渲染日志放 `C:\Users\<用户>\Documents\roughcut-<日期>-work\`，同时复制一份 EDL 到成片目录旁的 `粗剪工作区\`；共享电脑上另存 box 副本。
- 用户电脑偶尔“暂时连不上”：渲染已返回 pass JSON 时，以它为准；补充核对稍后重试。

## 3. 转录（faster-whisper）
- 模型 `small`，`language="zh"`，`word_timestamps=True`，CPU `int8`。13 分钟口播约 2–3 分钟转完。
- 装在 venv 里（不动系统 python）。faster-whisper 1.2.x 与新版 PyAV（如 19.x）不兼容，报 `open() got an unexpected keyword argument 'metadata_errors'`。修法二选一：
  - 用 `wave` 读 16k wav 成 float32 numpy 数组后直接传给 `transcribe`（`scripts/transcribe_words.py` 就是这么做的）；
  - 或 `pip install 'av<14'`。
- **VAD 会漏重复句**：`vad_filter=True` 会把轻声、紧挨着的重说并进静音或拉长成一个字。典型信号是一个词时间跨度 >1.5 秒（如“场@98.17-101.79”），或一段时间戳空洞。对这些区间用 `--no-vad`（并设 `condition_on_previous_text=False`）重转。10.25 那次的三遍重复就是这样才找出来的。
- `initial_prompt` 可放规范稿该处原句，提高识别率，但不要据此“补”出没说的话。
- ASR 错字很多（试纸→式子/狮子/市值，二甲→恶假，卵子→软子/泡泡）。判断重复看语义和时间结构，不按字面。

## 4. Windows 渲染
- 用 `python render_rough_cut.py --edl ... --output ... --encoder libx264`。`.ps1` 在 Windows PowerShell 5 下用 `ConvertFrom-Json` 读 UTF-8 中文 EDL 会报“无法识别的转义序列/无效 JSON”，因为 PS5 默认按 ANSI 读文件。
- 先 `--plan-only` 看段数和预计时长，再正式渲染。约 10 分钟 1080×1920 成片，libx264 在普通笔记本上要 6–8 分钟；工具调用要设足够的等待时间。
- 渲染前 `Test-Path` 目标文件，存在就停；每版新文件名。
- 渲染输出用 `> log 2>&1` 写日志，不要用 `Tee-Object` 管道：远程执行器的状态文件可能被占用而报错，但不影响渲染。

## 5. 验收
- 渲染脚本最后会输出 JSON：`status=pass`、`actual_duration_seconds`、编码、`full_decode=pass`。
- 再用 `ffprobe -show_entries stream=codec_type -show_entries format=duration` 核对音视频流和时长（与 EDL 合计误差 ≤1s；30 多段硬切通常多出 0.2–0.3s，属正常帧对齐）。
- 列出成片目录，确认旧版文件大小不变（没被覆盖）。
