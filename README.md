# ai_caption_video

一个面向中文短视频的“大字报/卡点字幕”生成工具。项目使用 Python、MoviePy、Pillow 和 FFmpeg 生成 9:16 黑底字幕视频，并支持本地 TTS 引擎按语音时长自动控制字幕片段。

## Features

- 多行文案输入：每一行生成一个字幕片段
- 1080x1920 竖屏黑底视频
- 大号中文粗体字幕居中显示
- 选中文字标记重点，视频中显示黄色并带心跳动效
- 随机字幕切换动画：缩小、滑出、竖起收起、倾斜缩小等
- 可选背景音乐，自动裁剪到视频长度并降低音量
- 可选 TTS：
  - Qwen3-TTS：调用本地 Qwen3-TTS 目录
  - F5-TTS：调用外部 F5-TTS 项目，支持参考音频和参考文本
- GUI 桌面界面
- PyInstaller 打包脚本

## Important

本仓库不包含任何 TTS 模型权重，也不分发生成的视频、音频、EXE 文件或用户配置。

如果使用 Qwen3-TTS、F5-TTS 或其他模型，请自行下载模型，并遵守对应项目和模型权重的许可证。

## Project Structure

```text
ai_caption_video/
  ai_caption_video/
    __init__.py
    __main__.py
    cli.py
    config.py
    f5_tts_bridge.py
    font_utils.py
    gui.py
    renderer.py
    text_utils.py
    tts_bridge.py
    video_builder.py
  assets/
    .gitkeep
  output/
    .gitkeep
  build_exe.ps1
  gui_entry.py
  input.txt
  requirements.txt
  setup_f5_tts.ps1
```

## Requirements

- Windows is the primary tested platform
- Python 3.10+
- FFmpeg available in `PATH`
- A Chinese font installed on Windows, such as Microsoft YaHei

Install Python dependencies:

```powershell
cd D:\ai_caption_video
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run CLI

```powershell
python -m ai_caption_video
```

Example:

```powershell
python -m ai_caption_video --input input.txt --output output/video.mp4 --keywords 人工智能,短视频,关键词
```

## Run GUI

```powershell
python gui_entry.py
```

The GUI supports:

- direct multiline script input
- selecting output directory
- marking highlighted text
- clearing all marks
- Qwen3-TTS or F5-TTS engine selection
- background music and custom font selection

Generated videos are named with timestamps, for example:

```text
20260616143022.mp4
```

## Qwen3-TTS

Qwen3-TTS is treated as an external local engine. The app calls the Python runtime inside the model project directory.

Default expected directory:

```text
\Qwen3-TTS-1.7B\Qwen3-TTS-1.7B
```

The app expects:

```text
\Qwen3-TTS-1.7B\Qwen3-TTS-1.7B\conda_env\python.exe
```

## F5-TTS

F5-TTS is also treated as an external local engine.

Suggested clone location:

```text
\F5-TTS
```

Clone manually:

```powershell
git clone https://github.com/SWivid/F5-TTS.git D:\Codex\workspaces\F5-TTS
```

Or use the helper script:

```powershell
.\setup_f5_tts.ps1
```

After setup, configure the GUI:

```text
TTS engine: F5-TTS
F5 project:\F5-TTS
F5 Python: \F5-TTS\.venv\Scripts\python.exe
Reference audio: your voice sample
Reference text: exact text spoken in the reference audio
```

F5-TTS generally requires a reference audio and matching reference text for stable voice cloning.

## Build EXE

```powershell
.\build_exe.ps1
```

The build output is written outside the repository:

```text
\ai_caption_video_exe\ai_caption_video.exe
```

The EXE does not include TTS model weights.

## GitHub Release Suggestion

Do not commit generated EXE files to the repository. If you want to distribute Windows builds, upload the EXE under GitHub Releases instead.

## License

MIT License. See [LICENSE](LICENSE).
