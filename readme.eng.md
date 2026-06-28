# AI Media Assistant Web

> **Transform your scripts into AI-powered videos — locally, privately, and efficiently.**

> **Formerly known as `ai_caption_video`**

AI Media Assistant is an open-source AI-powered video creation platform designed for content creators. It helps users transform scripts into professional subtitle videos with AI voice synthesis, automatic subtitle rendering, background image management, background music, and one-click video export.

Originally released as **ai_caption_video**, the project has been renamed to **AI Media Assistant** to reflect its broader vision of becoming a complete AI content creation platform.

Unlike cloud-based AI services, AI Media Assistant runs entirely on your local computer. All projects, generated videos, images, audio files, and configuration data remain under your control.

The built-in web interface is served only on **127.0.0.1**, making it ideal for creators who value privacy, offline workflows, and full ownership of their content.

---

# Screenshot

<p align="center">
  <img src="docs/images/main-gui.png" alt="AI Media Assistant Web" width="100%">
</p>

---

# Demo Videos

https://github.com/user-attachments/assets/1332d442-f919-4064-ad73-bb960943f4ea

https://github.com/user-attachments/assets/c6010d8a-5c08-4af2-81dc-150750757820

🎬 **Video Tutorial (Chinese)**

https://www.bilibili.com/video/BV18y7P66EAQ

A new tutorial series is currently being recorded and will be released soon.

---

# Features

## Local Web Editor

* Modern browser-based interface
* Project creation, duplication, deletion, and automatic saving
* No cloud dependency

## Script Management

* Multi-line script editing
* Each line is stored independently using UUID
* Images, colors, audio, and metadata are linked automatically

## Subtitle Templates

* Centered title style
* Queue subtitle style
* Chinese-style template
* Emotional subtitle template

## Automatic Background Images

* Automatically matches local background images for each sentence
* Prevents duplicate image usage within the same project

## Image Timeline

* Upload, replace, or delete background images for every sentence independently

## Keyword Highlighting

* Highlight important words inside subtitles
* Improve subtitle readability and visual impact

## Unified Rendering Engine

* Browser preview and exported videos share the same rendering pipeline
* Consistent subtitle layout and image cropping

## AI Voice Synthesis

Supports multiple TTS engines:

* OmniVoice
* Qwen3-TTS
* Reference audio cloning
* Preset voices
* Adjustable speech rate

## Background Music

* Built-in music library
* Random BGM selection
* Custom BGM upload
* Adjustable volume

## Background Workers

* Video rendering
* AI voice generation
* Non-blocking task execution

## Task Manager

* Task status monitoring
* Retry failed tasks
* Cancel running tasks
* Preview generated videos
* Download finished videos

## Local Resource Management

Supports local management of:

* Background images
* Voice presets
* BGM library
* Fonts
* Logo assets
* Subtitle templates

---

# Project Architecture

```text
apps/
  web/                 React + TypeScript + Vite frontend
  api/                 FastAPI + SQLAlchemy + Alembic backend

workers/
  render_worker/       Video rendering and TTS worker

packages/
  media_core/          Subtitle engine, templates, TTS bridge,
                       video rendering and media processing

storage/
  resources/           Distributable local resources
  projects/            SQLite database and TTS cache
  uploads/             User uploaded assets
  outputs/             Exported videos
```

---

# Quick Start

## Windows

Run the setup script for the first launch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Start the application:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
```

Open your browser:

```text
http://127.0.0.1:8123
```

---

## macOS

Grant execution permissions:

```bash
chmod +x scripts/setup_macos.sh scripts/start_macos.sh
```

Run the setup:

```bash
./scripts/setup_macos.sh
```

Launch the application:

```bash
./scripts/start_macos.sh
```

Open:

```text
http://127.0.0.1:8123
```

---

# System Requirements

* Windows 10 / Windows 11
* macOS
* Python 3.11 or later
* Node.js 20 or later
* FFmpeg (recommended in system PATH)

Optional:

* OmniVoice
* Qwen3-TTS

Model files are **NOT** included in this repository or Release packages.

Users need to prepare the model environment separately.

Model paths can be configured inside **Settings**.

---

# Recommended Model Directory

```text
ai-media-assistant/

models/

    OmniVoice/

        .venv/bin/python             macOS

        .venv/Scripts/python.exe     Windows

        omnivoice/

        ...

    Qwen3-TTS-1.7B/

        .venv/bin/python             macOS

        conda_env/python.exe         Windows

        qwen/

        qwen_tts/

        ...
```

Windows and macOS model environments are **NOT** compatible.

Windows Python environments cannot run on macOS, and vice versa.

---

# Local Resources

Release packages may include:

```text
storage/resources/

    ancient/

    bg_B-Roll_Senior_Emotions/

    bg_elder_person/

    bgm_library/

    fonts/

    voice/
```

The following folders are generated during runtime and should **NOT** be committed to Git or included in public releases:

```text
storage/projects/

storage/uploads/

storage/outputs/

models/

.venv/

node_modules/
```

---

# Local Development

After completing the setup script, start development mode:

```bash
npm run dev
```

Development services:

| Service      | URL                              |
| ------------ | -------------------------------- |
| Web UI       | http://127.0.0.1:5173            |
| API Docs     | http://127.0.0.1:8123/docs       |
| Health Check | http://127.0.0.1:8123/api/health |

The Worker automatically processes:

* AI voice generation
* Video rendering

---

# Production Build

Build the frontend:

```bash
npm run build
```

Serve using FastAPI:

```bash
npm run serve
```

Open:

```text
http://127.0.0.1:8123
```

---

# Testing

```bash
npm test

npm run build
```

---

# Release Packaging

Windows maintainers can package a Release using:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package_release.ps1 -Version v2.0.0
```

Default output:

```text
D:\Codex\outputs\ai-media-assistant.zip
```

The packaging script automatically includes:

* Built frontend
* Distributable resources
* Fonts
* BGM
* Templates

It automatically excludes:

* SQLite databases
* Generated videos
* User uploads
* Cache files
* Virtual environments
* Node dependencies
* AI model files

---

# Roadmap

## Community Edition

* ✅ Local Web Editor
* ✅ Subtitle Templates
* ✅ AI Voice Generation
* ✅ Background Music
* ✅ Video Rendering
* ✅ Background Workers

## Coming Soon

* AI Media Assistant Cloud (SaaS)
* Mobile App
* Cloud Rendering
* AI Image Generation
* Storyboard Generation
* AI Agent Integration
* Team Collaboration
* Online Project Synchronization

---

# Contributing

Contributions, Issues, and Pull Requests are always welcome.

If you find this project useful, please consider giving it a ⭐ on GitHub.

Your support helps the project continue to grow.

---

# License

This project is released under the license specified in the **LICENSE** file.
