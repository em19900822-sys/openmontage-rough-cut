# OpenMontage Rough Cut

一个面向中文口播视频的 Codex Skill。它根据逐字稿和逐词时间戳，保守删除重复重说、失败起句与明显重录，再把多个原始片段快速合并成第一版粗剪。

## 适用场景

- 多个真人口播片段需要按顺序连接
- 只删除明确重复和失败录制
- 第一版不需要字幕、美颜、音乐、辅助画面或转场
- 使用 FFmpeg + Python（Linux/macOS/Windows 通用）或 Windows PowerShell 本地完成；也覆盖按客户成片时间点的多轮返修

## 安装

把本仓库克隆到 Codex Skill 目录：

```powershell
git clone https://github.com/em19900822-sys/openmontage-rough-cut.git "$HOME\.codex\skills\openmontage-rough-cut"
```

重新打开 Codex 后，可以直接调用：

```text
$openmontage-rough-cut
```

## 使用示例

```text
用 $openmontage-rough-cut 粗剪这个文件夹里的三个口播片段。
只删除重复重说，把三个片段连接起来，不加字幕和美颜。
逐字稿在这个飞书链接，成片保存到 D:\output\粗剪01。
```

## 文件

- `SKILL.md`：任务判断、删除边界和验收标准
- `scripts/render_rough_cut.ps1`：按 EDL 精确裁切、拼接和完整解码检查
- `tests/test_render_rough_cut.ps1`：渲染计划接口测试
- `agents/openai.yaml`：Codex 中的显示和调用配置

## 本地依赖

- Windows PowerShell 7
- FFmpeg 与 FFprobe
- OpenMontage 项目，用于工程管理、转录复用和后续精剪

渲染脚本优先使用 Intel QSV；不可用时自动切换到 `libx264 veryfast`。

## 设计原则

- 漏删优于误删
- 保留独有观点、条件、例子和行动建议
- 不把转录识别错误当成口误
- 不覆盖原始视频
- 只有完整解码通过后才报告完成
