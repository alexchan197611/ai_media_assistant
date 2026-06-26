# ai_media_assistant

面向中文内容创作者的本地 Web 媒体生产工具。项目第一阶段将现有 `ai_caption_video` 桌面版能力迁移到浏览器，并为后续 TTS、智能配图、模板市场和云端部署保留扩展空间。

## 当前状态

Phase 0 工程基础已完成，并已开始向桌面版 `ai_caption_video v1.0.2` 的核心生产能力迁移：React 编辑器、FastAPI API、SQLite 数据模型、Alembic 迁移、项目 CRUD、UUID 片段同步、自动保存和后台 Worker 边界均已建立；旧版非 GUI 的渲染、TTS、OmniVoice、BGM 选择等核心模块已接入 `media_core`，并通过后台任务 API 调用。

- 产品需求文档：[docs/PRD.md](docs/PRD.md)
- 旧项目能力来源：`ai_caption_video v1.0.2`
- 推荐形态：本地 Web 应用，浏览器编辑，Python 服务调用本机模型与 FFmpeg

## 规划目录

```text
ai_media_assistant/
  apps/
    web/                 # React + TypeScript 前端
    api/                 # FastAPI HTTP/WebSocket API
  workers/
    render_worker/       # TTS、渲染和导出任务执行器
  packages/
    media_core/          # 字幕排版、模板、时间轴、音视频合成核心
  docs/
    PRD.md
  storage/
    projects/            # 本地项目数据
    uploads/             # 用户上传素材
    outputs/             # 导出视频
```

## 当前可用能力

- 项目创建、打开、编辑、删除和自动保存。
- 多行文案同步为独立 UUID 片段。
- 旧桌面版字幕渲染核心、三类模板渲染函数、Qwen3-TTS bridge、OmniVoice bridge 和 BGM 随机选择逻辑已迁移到 `packages/media_core`。
- 后端提供模型状态检测、TTS 队列、渲染队列和任务状态查询接口。
- 后端提供统一静态预览 PNG，复用桌面版字幕渲染核心，前端预览不再自行实现换行和重点词排版。
- 后端支持单句 TTS 任务、整项目 TTS 任务、渲染任务结果素材回写和项目输出视频列表。
- 后端支持任务列表、SSE 事件流、取消和重试；Worker 可从 SQLite 队列消费 `tts_segment`、`tts_all` 和 `render` 任务，调用原有位置的 Qwen/OmniVoice 模型与 MoviePy 渲染链路。
- 编辑器可触发“生成/重生成本句”“生成全部配音”和“后台导出 MP4”，并显示实时任务中心；生成后的单句音频可在片段面板试听，导出视频可在输出区播放或下载。
- 项目首页支持复制项目：保留文案、模板、重点词、颜色、配图和设置，重新生成项目 ID 与片段 UUID，不复用历史音频或输出视频。
- 逐句配图支持主体位置调整；后端预览和最终导出共享同一裁切焦点、运镜和字幕渲染核心。
- 编辑器支持当前片段低分辨率动态预览 GIF，播放按钮可查看字幕入场、过场、运镜和古风烟雾等后端渲染动画。
- API 提供 Worker 在线状态检测；Worker 启动后写入本地 heartbeat，异常退出遗留的运行中任务会在下次启动时标记为失败并允许重试。
- BGM 支持读取旧桌面项目内置音乐库、手动选择曲目、随机选曲、上传自定义音乐、填写 BPM 和调整音量；导出时可按 BPM 对句间边界做保守卡点微调，不缩短任何 TTS 音频。
- 古风参考音色、古风字体、古风背景和内置 BGM 库已迁入 `storage/resources`，运行时不再依赖旧桌面项目目录；这些本地资源被 `.gitignore` 排除，不会提交到 Git。

仍在迁移中的 1.0.2 等价功能：

- 重点词标记 UI 和逐句颜色/图片的完整编辑面板。
- 素材上传、缩略图、裁切主体位置和参考音频上传。
- 多片段连续预览播放、逐句播放头、任务运行中的模型子进程硬中断、真实节拍检测和更细粒度模型/渲染进度仍需继续完善。

## 第一阶段目标

在浏览器中完成文案编辑、重点词标记、逐句配图、模板预览、TTS 配音、BGM 选择与视频导出，达到现有桌面版主要能力的 Web 化可用版本。

## 开发原则

- 模型权重、商业字体、用户音色和输出视频不提交 Git。
- 前端预览与最终视频共享同一份项目数据和排版规则。
- 耗时任务必须进入后台队列，不阻塞 API 请求。
- 所有生成结果可追踪、可取消、可重试，不覆盖历史文件。

## 本地开发

要求 Node.js 20+ 和 Python 3.11+。Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
npm install
npm --prefix apps/web install
npm run db:upgrade
npm run dev
```

统一启动命令会同时启动：

- Web：`http://127.0.0.1:5173`
- API 文档：`http://127.0.0.1:8123/docs`
- 健康检查：`http://127.0.0.1:8123/api/health`
- Worker：后台消费 TTS 和视频渲染任务

服务默认仅监听 `127.0.0.1`。`npm run dev` 会同时启动 API、Web 和 Worker；如果只启动 API/Web 而未启动 Worker，任务只会排队，编辑器会显示 Worker 离线提示。TTS 模型默认继续使用本机现有位置，例如 `E:\Qwen3-TTS-1.7B\Qwen3-TTS-1.7B` 和 `D:\Codex\workspaces\OmniVoice`，也可通过项目 `tts_settings` 覆盖。

`npm run dev` 默认使用稳定单进程 API 启动方式；前端保留 Vite 热更新，后端代码改动后重新运行启动命令即可。

本地运行资源目录：

```text
storage/resources/
  ancient/       # 古风背景和参考音色
  fonts/         # 古风字体和开源兜底字体
  bgm_library/   # 内置 BGM 曲库
```

这些资源用于本机运行，但不提交 Git。

构建前端后，也可以用一个本地 API 地址直接访问 Web UI：

```powershell
npm run build
npm run serve
```

打开：

```text
http://127.0.0.1:8123
```

如需单独调试某个进程：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8123
$env:AMA_API_TARGET="http://127.0.0.1:8123"; npm --prefix apps/web run dev -- --host 127.0.0.1
npm run worker
```

## 测试

```powershell
npm test
npm run build
```

SQLite 文件及上传、输出、模型、字体和用户音色均受 `.gitignore` 保护，不会进入版本库。
