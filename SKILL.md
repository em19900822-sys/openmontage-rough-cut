---
name: openmontage-rough-cut
description: Use when the user wants a fast first rough cut of several local talking-head clips in OpenMontage by removing repeated takes, failed starts, and obvious restarts, then joining the retained speech without subtitles, beauty, music, overlays, or decorative transitions.
---

# OpenMontage 口播粗剪

交付一个可直接观看和继续精剪的第一版。只处理明确重复与失败录制，保留所有独有观点和自然表达。

## 输入

- 一个包含多个本地视频片段的文件夹；按文件名或用户指定顺序连接。
- 逐字稿可以来自飞书、用户提供的文本或已有本地逐词转录。
- 用户指定的输出目录。未指定时必须先询问，不能自行选择长期保存位置。

## 执行流程

1. 先读 OpenMontage 项目内的 `AGENTS.md` 和 `AGENT_GUIDE.md`。已有同主题项目、转录、EDL 或 checkpoint 时继续使用，不重新转录。
2. 探测全部源视频，确认可读、音轨存在、显示方向、分辨率、帧率和时长。保留原始素材，不移动、不覆盖。
3. 有飞书逐字稿链接时，按 `lark-shared`、`lark-wiki`、`lark-doc` 读取正文；只读操作直接执行。
4. 优先复用逐词时间戳。没有时间戳时，使用已配置的本地或免费额度转录路线；任何新增付费调用必须先取得用户明确同意。
5. 建立 EDL。每个保留片段至少包含：`order`、`input_path`、`start_seconds`、`end_seconds`、`reason`。
6. 使用 [scripts/render_rough_cut.ps1](scripts/render_rough_cut.ps1) 一次完成精确裁切与硬切合并。默认先尝试 Intel QSV，失败后自动改用 `libx264 veryfast`。
7. 把通过检查的成片复制到用户指定目录。工程 Master 与交付副本计算 SHA256，必须一致。

## 删除判断

删除：

- 同一句连续录了多遍，保留最后一次完整、清楚的版本。
- 说到一半停住，随后从句首完整重说。
- 接错上一句后重新开始的失败起句。
- 同一比喻、案例或结论原样回说。
- 明显的开拍倒数、试音和无内容口令。

保留：

- 新观点、条件、例子、边界和行动建议。
- 不影响理解的自然语气词和短停顿。
- 只有相似但承担不同衔接作用的句子。
- 无法确认是否重复的内容。漏删优于误删。

不要为了逐字匹配规范稿而删掉真实口播中的独有信息。不要把转录识别错误当成口误直接删除。

## 粗剪边界

除非用户另行要求，本 Skill 必须保持：

- 无字幕
- 无美颜与调色
- 无音乐、音效和辅助画面
- 无变速
- 无淡入淡出或花式转场，只使用硬切
- 不激进压缩停顿

这只是第一版粗剪，不执行完整成片的 Style Lock、字幕对齐、美颜或发布流程。

## EDL 示例

```json
{
  "version": "rough-cut-v1",
  "segments": [
    {
      "order": 1,
      "input_path": "D:/footage/01.MOV",
      "start_seconds": 3.02,
      "end_seconds": 47.98,
      "reason": "保留完整开头，删除随后重复的一遍"
    }
  ]
}
```

先检查计划：

```powershell
& "$SKILL_DIR\scripts\render_rough_cut.ps1" `
  -EdlPath "D:\project\artifacts\rough_cut_v1_edl.json" `
  -OutputPath "D:\output\粗剪第一版.mp4" `
  -PlanOnly
```

正式渲染：

```powershell
& "$SKILL_DIR\scripts\render_rough_cut.ps1" `
  -EdlPath "D:\project\artifacts\rough_cut_v1_edl.json" `
  -OutputPath "D:\output\粗剪第一版.mp4"
```

## 完成标准

- 输出含一个视频流和一个音频流，可完整解码。
- 输出时长与 EDL 保留时长误差不超过 1 秒。
- 顺序与 EDL 一致，重复内容已删除，独有观点无缺失。
- 没有字幕、美颜、音乐、辅助画面或额外转场。
- 源文件保持原样。
- 交付文件真实存在于用户指定路径，并报告时长、规格和未确认事项。
