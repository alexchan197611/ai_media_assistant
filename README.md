# ai_caption_video

一个面向中文短视频创作者的“大字报 / 卡点字幕”生成工具。

项目使用 Python、MoviePy、Pillow 和 FFmpeg 生成 9:16 竖屏视频，并可调用本地 TTS 模型生成配音，让字幕时长自动跟随语音。

当前版本：`v1.0.2`

## 项目预览

![软件主界面](images/gui-main.png)

<p align="center">
<a href="images/demo.mp4">
  <img src="images/demo.png" width="360" alt="点击观看演示视频">
</a>
<a href="images/demo.mp4">
  <img src="images/demo2.png" width="360" alt="点击观看古风模板演示视频">
</a>
</p>

- [直接打开演示视频 demo.mp4](images/demo.mp4)
- [观看 B 站视频演示](https://www.bilibili.com/video/BV1A9Ld6BEf8)

  我也封装好了EXE，各位懒得自己编译的，到B站视频评论区里看看夸克网盘下载链接。

## 主要功能

- 多行文案输入，每一行生成一个字幕片段
- 默认1080×1920、9:16 竖屏视频
- 大号粗体中文字幕
- 手机比例实时预览，可查看文字换行效果
- 支持调整字体、字号、分辨率和 FPS
- 支持选中文字并标记为黄色重点词
- 重点词支持心跳动效，心跳速度可调
- 每一行可以单独设置字幕颜色
- 每一行可以单独绑定背景图片
- 未设置图片的字幕片段自动使用黑色背景
- 背景图片自动裁切为 9:16，并随机应用轻微推拉和平移运镜
- 支持“滚动队列”和“居中大字”字幕模板
- 支持“古风模板”：水墨背景、毛笔字体、传统竖排和逐字落墨
- 古风字幕根据每句 TTS 时长从上到下逐字出现，标点自动形成停顿
- 古风模板中的重点词使用朱砂红显示
- 软件默认使用 OmniVoice 的语音克隆模式
- 古风模板内置专用参考音色，切换模板时自动联动
- 软件启动时默认最大化窗口
- 支持缩小、滑出、竖起、倾斜等字幕切换动画
- 支持手动选择背景音乐
- 提供本地音乐库随机选曲，并让句间切换尽量贴合鼓点
- 支持 Qwen3-TTS 和 OmniVoice 本地 TTS
- 支持预设人声、语音设计和语音克隆【推荐使用语音克隆】
- 生成的视频使用时间戳命名，不覆盖历史文件
- 提供 PyInstaller EXE 打包脚本

## 重要说明

本源码仓库不包含以下内容：
- Qwen3-TTS 模型
- OmniVoice 模型

使用或分发第三方模型、音乐和字体前，请确认并遵守对应项目的许可证及商业使用条款。

## 项目结构

```text
ai_caption_video/
  ai_caption_video/
    __init__.py
    __main__.py
    cli.py
    config.py
    font_utils.py
    gui.py
    music_library.py
    omnivoice_bridge.py
    renderer.py
    text_utils.py
    tts_bridge.py
    video_builder.py
  assets/
    .gitkeep
    ancient/
      ancient_background.png  # 本地/Release 构建资源，不提交公开仓库
      ancient_voice.wav       # 本地/Release 构建资源，不提交公开仓库
    bgm_library/       # 可选的本地 BGM 音乐库
    fonts/
      HYShangWeiShouShu.ttf  # 授权后自行放入，不提交公开仓库
      ZhiMangXing-Regular.ttf
      OFL.txt
  images/
    gui-main.png
    demo.png
    demo2.png
    demo.mp4
  output/
    .gitkeep
  build_exe.ps1
  gui_entry.py
  input.txt
  requirements.txt
```

## 运行环境

- Windows 10 或 Windows 11
- Python 3.10 及以上版本
- FFmpeg
- Windows 中文字体，例如微软雅黑

安装 Python 依赖（建议将项目放置到D盘 ai_caption_video目录下）：

```powershell
cd D:\ai_caption_video
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 启动 GUI

```powershell
python gui_entry.py
```

GUI 支持：

- 直接输入或粘贴多行中文文案
- 标记或取消重点词
- 设置每行字幕颜色
- 为当前行选择或清除背景图片
- 在手机预览框中查看图片和字幕组合效果
- 选择字幕模板
- 手动选择 BGM，或启用“随机匹配并卡点”
- 在 Qwen3-TTS 和 OmniVoice 之间切换
- 选择输出目录

生成的视频使用时间戳命名，例如：

```text
20260616143022.mp4
```

### 古风模板

选择“古风模板”后：

- 未设置配图时使用内置水墨暗角背景
- 设置配图后自动应用灰阶、冷墨色调和暗角处理
- 优先使用授权的“汉仪尚巍手书”，缺少该文件时回退到内置毛笔字体
- 默认使用项目内置古风背景，并在背景之上、文字之下叠加贯穿全片的稀薄动态烟雾
- 字幕从上到下逐字出现，每列最多 7 个字，内容过长时从右向左增加新列
- 短句会按可用文字区域自动放大，长句则自动缩小以保持版面稳定
- 逗号、句号、问号等标点不绘制，但会产生不同长度的朗读停顿
- 普通文字使用墨黑色，标记重点使用朱砂红
- 字符位置会预先固定，逐字出现时不会改变行距或发生跳动

古风背景、古风参考音频和 `assets/fonts` 中实际存在的字体会通过 PyInstaller 直接打包进 EXE。商业字体请在取得授权后命名为 `HYShangWeiShouShu.ttf` 放入该目录；开源仓库仅保留可再分发的回退字体，其许可证位于 `assets/fonts/OFL.txt`。

切换到“古风模板”时，软件会自动：

- 启用 TTS
- 切换到 OmniVoice
- 切换到“语音克隆”模式
- 使用内置 `ancient_voice.wav` 作为参考音频
- 填入内置参考文案
- 隐藏“行颜色”设置，普通文字固定为墨黑色，重点文字固定为朱砂红

## 命令行运行

```powershell
python -m ai_caption_video
```

示例：

```powershell
python -m ai_caption_video --input input.txt --output output/video.mp4 --keywords 人工智能,短视频,关键词
```

## Qwen3-TTS

软件优先识别 EXE 同级目录下的 portable 模型：

```text
models\Qwen3-TTS-1.7B
```

支持的能力：

- **预设人声**：Aiden、Dylan、Eric、Ono_anna、Ryan、Serena、Sohee、Uncle_fu、Vivian
- **语音设计**：通过文字描述声音、情绪和朗读风格
- **语音克隆**：上传参考音频并填写参考文本，也可仅使用 x-vector

Qwen3-TTS 使用隐藏的常驻后台进程。第一次生成时需要加载模型，耗时较长；软件不关闭时，后续生成会复用已经加载的模型。

Qwen3-TTS 暂不提供语速调整，因为后期变速可能产生回响和音质下降。

## OmniVoice

portable 整合包目录：

```text
models\OmniVoice
```

portable 运行时需要保留：

```text
models\OmniVoice\.python\python.exe
models\OmniVoice\.venv
models\OmniVoice\hf_cache
models\OmniVoice\omnivoice
```

支持的能力：

- **自动音色**：由 OmniVoice 自动选择音色
- **语音设计**：使用文字描述需要的声音风格
- **语音克隆**：上传参考音频，参考文本可以选填
- **语速控制**：使用 OmniVoice 原生 `speed` 参数
- **生成步数**：可调整 `num_step`

## 本地 BGM 音乐库

将音乐文件放入：

```text
assets\bgm_library
```

软件支持 MP3、WAV、M4A 和 FLAC。启用“随机匹配并卡点”后，软件会随机选择一首音乐，并根据文件名中的 BPM 信息让句间切换尽量贴合鼓点。

推荐文件名：

```text
healing_story_76bpm.mp3
knowledge_clean_92bpm.mp3
business_growth_106bpm.mp3
viral_fast_124bpm.mp3
suspense_reveal_132bpm.mp3
```

## 打 EXE

```powershell
.\build_exe.ps1
```


## 许可证

本项目采用 MIT License，详情请查看 [LICENSE](LICENSE)。
