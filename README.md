# ai_media_assistant

面向中文内容创作者的本地 Web 媒体生产工具。项目第一阶段将现有 `ai_caption_video` 桌面版能力迁移到浏览器，并为后续 TTS、智能配图、模板市场和云端部署保留扩展空间。

## 当前状态

项目已建立，当前处于需求定义阶段。

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

## 第一阶段目标

在浏览器中完成文案编辑、重点词标记、逐句配图、模板预览、TTS 配音、BGM 选择与视频导出，达到现有桌面版主要能力的 Web 化可用版本。

## 开发原则

- 模型权重、商业字体、用户音色和输出视频不提交 Git。
- 前端预览与最终视频共享同一份项目数据和排版规则。
- 耗时任务必须进入后台队列，不阻塞 API 请求。
- 所有生成结果可追踪、可取消、可重试，不覆盖历史文件。
