# AI Media Assistant 开发约定

## 产品上下文

- 本项目是 `ai_caption_video` 的独立 Web 化项目，不在原桌面项目中继续开发。
- 产品需求以 `docs/PRD.md` 为准。
- 第一阶段采用本地 Web 架构：浏览器编辑，Python 服务调用本机 TTS、MoviePy、Pillow 和 FFmpeg。
- MVP 不做公共云 SaaS、多用户协作、付费和专业多轨时间轴。

## 推荐技术栈

- `apps/web`: React + TypeScript + Vite
- `apps/api`: FastAPI + Pydantic + SQLAlchemy + Alembic
- `workers/render_worker`: 独立后台任务进程
- `packages/media_core`: 与 Web 框架无关的字幕、模板、TTS 和渲染核心
- MVP 数据库：SQLite

## 关键约束

- 每条文案行必须使用 UUID 保存关联数据，禁止用数组下标持久化颜色、图片或音频。
- 前端预览与最终导出必须共享同一布局结果，禁止分别实现两套换行规则。
- TTS 和视频渲染必须运行在后台 Worker，不阻塞 FastAPI 请求。
- 模型进程应常驻复用，第一次加载时通过任务状态明确告知用户。
- 模型权重、商业字体、用户音色、上传素材和生成视频不得提交 Git。
- 默认服务仅监听 `127.0.0.1`。

## 建议开发顺序

1. 初始化 React、FastAPI 和共享开发脚本。
2. 建立 Project、Segment、Asset、Job 数据模型与数据库迁移。
3. 完成项目 CRUD、多行文案同步和自动保存。
4. 抽取旧项目的字幕布局与静态预览能力到 `media_core`。
5. 完成逐句图片上传和 9:16 预览。
6. 接入后台任务、TTS Adapter 和进度事件。
7. 接入视频渲染、BGM 和历史输出。
8. 最后迁移古风模板、烟雾动画和模板联动行为。

## 旧项目参考

旧项目默认位于：

```text
D:\Codex\workspaces\ai_caption_video
```

迁移代码前先阅读并补测试，不直接复制桌面 GUI 状态管理逻辑。
