# AI Media Assistant Web 2.0 使用说明

AI Media Assistant 是本地运行的短视频生成工具。浏览器负责编辑，Python 后端负责 TTS、字幕、配图、BGM 和视频渲染。

## 1. 安装依赖

请先安装：

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- FFmpeg，建议加入系统 PATH
- 可选：OmniVoice / Qwen3-TTS 模型环境

安装 Python 时建议勾选 `Add python.exe to PATH`。

## 2. 首次安装

解压 Release 压缩包后，在项目目录空白处右键打开 PowerShell，执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

脚本会自动完成：

- 创建 `.venv`
- 安装 Python 依赖
- 安装 Node 依赖
- 构建 Web 前端
- 初始化 SQLite 数据库
- 创建本地存储目录

## 3. 启动软件

执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
```

浏览器打开：

```text
http://127.0.0.1:8123
```

服务默认只监听 `127.0.0.1`，不会对外网开放。

## 4. 基本使用流程

1. 点击“新建”创建项目。
2. 在左侧文案框输入多行文案，每一行会成为一个独立片段。
3. 选择字幕模板，例如“情感模板”。
4. 情感模板会根据每行文字自动匹配背景图。
5. 在“片段配图”轨道中可以上传、修改或删除每一句背景图。
6. 选择 TTS 引擎和预设语音。
7. 选择 BGM 或随机音乐。
8. 点击“开始生成”。
9. 生成完成后，可在右侧预览视频并下载 MP4。

## 5. 资源目录

Release 包会包含可分发资源：

```text
storage/resources/
  ancient/                     古风参考资源
  bg_B-Roll_Senior_Emotions/   情感模板背景图
  bg_elder_person/             老年人背景图
  bgm_library/                 内置 BGM
  fonts/                       可分发字体
  voice/                       预设语音
```

运行中产生的内容不会提交到 Git：

```text
storage/projects/              SQLite 数据库与 TTS 缓存
storage/uploads/               用户上传素材
storage/outputs/               导出视频
```

## 6. 模型位置

右上角“设置”中可以配置：

- Qwen 模型位置
- OmniVoice 模型位置

留空时软件会使用默认搜索位置。推荐把模型放在软件根目录的 `models` 文件夹：

```text
ai-media-assistant/
  models/
    OmniVoice/
    Qwen3-TTS-1.7B/
```

macOS 用户不要使用 Windows 模型包。Windows 包里的 `python.exe`、`.dll`、`.pyd` 不能在 macOS 上运行。Mac 可用模型包解压后，目录里应能看到：

```text
models/OmniVoice/.venv/bin/python
models/Qwen3-TTS-1.7B/.venv/bin/python
```

如果不小心把 Windows 模型包放到 Mac，软件会提示“检测到 Windows 版模型运行环境”。这时需要换成 macOS arm64 版模型包。

## 7. 常见问题

### 页面打不开

确认 `start_windows.ps1` 仍在运行，并访问：

```text
http://127.0.0.1:8123
```

### 点击生成后一直排队

说明 Worker 没有启动或异常退出。关闭 PowerShell 后重新运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
```

### 没有声音或 TTS 失败

检查右上角“设置”里的模型状态，以及参考音频/预设语音是否存在。

### 视频导出失败

确认 FFmpeg 可用：

```powershell
ffmpeg -version
```

如不可用，请安装 FFmpeg 并加入 PATH。

## 8. 发布到视频号

当前版本会生成本地 MP4。建议先手动上传到视频号助手。后续版本可增加“发布助手”，自动准备标题、简介、标签和封面图。
