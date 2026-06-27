# macOS 模型包制作说明

Windows 模型包不能直接给 macOS 使用。原因是模型包里的 Python 环境包含 `python.exe`、`.dll`、`.pyd` 等 Windows 二进制文件，macOS 需要重新生成 `.venv/bin/python` 和对应的 macOS/arm64 依赖。

本目录提供维护者在 Mac 电脑上制作模型包的脚本。制作完成后，用户只需要把模型包解压到软件目录的 `models` 文件夹即可使用。

## 目标目录

最终用户目录应是：

```text
ai-media-assistant/
  models/
    OmniVoice/
      .venv/bin/python
      omnivoice/
      hf_cache/
      ...
    Qwen3-TTS-1.7B/
      .venv/bin/python
      Qwen/
      qwen_tts/
      ...
```

## 制作步骤

在 Mac 上解压 AI Media Assistant，然后把现有模型的源码和权重复制到：

```text
models/OmniVoice
models/Qwen3-TTS-1.7B
```

不要复制 Windows 虚拟环境目录，例如：

```text
.python/
.venv/
venv/
conda_env/
```

然后在项目根目录执行：

```bash
chmod +x scripts/macos_models/*.sh
./scripts/macos_models/build_all_macos.sh
```

脚本会生成：

```text
dist/OmniVoice-macos-arm64.zip
dist/Qwen3-TTS-1.7B-macos-arm64.zip
dist/ai-media-assistant-models-macos-arm64.zip
```

可以分别发布两个模型包，也可以发布合包。用户解压后把里面的 `OmniVoice` 和 `Qwen3-TTS-1.7B` 放进软件的 `models` 目录即可。

## 注意

- 推荐 Apple Silicon Mac，Python 3.11 或 3.12。
- 如果用户是 Intel Mac，需要在 Intel Mac 上重新执行这些脚本，不能复用 arm64 包。
- 第一次构建会下载 PyTorch、Transformers 等依赖，耗时较长。
- Qwen3-TTS 和 OmniVoice 的权重文件不在公开源码包内，请只在你有权分发的范围内打包。
