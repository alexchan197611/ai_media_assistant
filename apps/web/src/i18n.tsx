import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type Language = 'zh' | 'en'

const storageKey = 'ai_media_assistant_lang'

type Dictionary = Record<string, { zh: string; en: string }>

const dictionary: Dictionary = {
  'app.untitled': { zh: '未命名视频', en: 'Untitled video' },
  'app.loadFailed': { zh: '项目加载失败。', en: 'Failed to load project.' },
  'app.backHome': { zh: '返回首页', en: 'Back to home' },
  'app.openingEditor': { zh: '正在打开编辑器…', en: 'Opening editor...' },
  'app.deleteConfirm': { zh: '确定删除这个项目吗？', en: 'Delete this project?' },
  'api.requestFailed': { zh: '请求失败', en: 'Request failed' },
  'api.uploadFailed': { zh: '上传失败', en: 'Upload failed' },
  'common.new': { zh: '新建', en: 'New' },
  'common.settings': { zh: '设置', en: 'Settings' },
  'common.cancel': { zh: '取消', en: 'Cancel' },
  'common.retry': { zh: '重试', en: 'Retry' },
  'common.delete': { zh: '删除', en: 'Delete' },
  'common.upload': { zh: '上传', en: 'Upload' },
  'common.modify': { zh: '修改', en: 'Change' },
  'common.download': { zh: '下载', en: 'Download' },
  'common.clear': { zh: '清除', en: 'Clear' },
  'common.default': { zh: '默认', en: 'Default' },
  'common.available': { zh: '可用', en: 'Available' },
  'common.unavailable': { zh: '不可用', en: 'Unavailable' },
  'common.chooseFile': { zh: '选择文件', en: 'Choose file' },
  'common.modifyFile': { zh: '修改文件', en: 'Change file' },
  'common.notSet': { zh: '未设置', en: 'Not set' },
  'common.localMachine': { zh: '本机', en: 'Local' },
  'common.language': { zh: '语言', en: 'Language' },
  'home.newProject': { zh: '新建项目', en: 'New project' },
  'home.recentProjects': { zh: '最近项目', en: 'Recent projects' },
  'home.subtitle': { zh: '继续创作，或从一段新文案开始。', en: 'Keep creating, or start from a fresh script.' },
  'home.loading': { zh: '正在读取本地项目…', en: 'Reading local projects...' },
  'home.emptyTitle': { zh: '创建你的第一条视频', en: 'Create your first video' },
  'home.emptyBody': { zh: '输入多行文案，每行都会成为独立片段。', en: 'Enter multi-line copy. Each non-empty line becomes its own segment.' },
  'home.newBlankProject': { zh: '新建空白项目', en: 'New blank project' },
  'home.openProject': { zh: '打开项目', en: 'Open project' },
  'home.duplicateProject': { zh: '复制项目', en: 'Duplicate project' },
  'home.deleteProject': { zh: '删除项目', en: 'Delete project' },
  'save.saved': { zh: '已自动保存', en: 'Auto-saved' },
  'save.saving': { zh: '正在保存…', en: 'Saving...' },
  'save.dirty': { zh: '等待保存…', en: 'Waiting to save...' },
  'save.error': { zh: '保存失败', en: 'Save failed' },
  'editor.backProjects': { zh: '返回项目', en: 'Back to projects' },
  'editor.projectName': { zh: '项目名称', en: 'Project name' },
  'editor.script': { zh: '文案', en: 'Script' },
  'editor.segmentCount': { zh: '{count} 个片段', en: '{count} segments' },
  'editor.scriptAria': { zh: '多行文案', en: 'Multi-line script' },
  'editor.scriptPlaceholder': { zh: '在这里输入文案\n每个非空行会成为一个片段', en: 'Enter your script here\nEach non-empty line becomes a segment' },
  'editor.markImportant': { zh: '标记重点', en: 'Mark important' },
  'editor.removeSelectedMark': { zh: '取消选中标记', en: 'Remove selected mark' },
  'editor.clearMarks': { zh: '清空重点', en: 'Clear marks' },
  'editor.templatePanel': { zh: '模板与画面', en: 'Template & Visuals' },
  'editor.subtitleTemplate': { zh: '字幕模板', en: 'Subtitle template' },
  'editor.template.centered': { zh: '居中大字', en: 'Centered bold' },
  'editor.template.scrolling': { zh: '滚动队列', en: 'Scrolling queue' },
  'editor.template.ancient': { zh: '古风模板', en: 'Ancient style' },
  'editor.template.emotion': { zh: '情感模板', en: 'Emotion template' },
  'editor.currentSegment': { zh: '当前片段 {index}', en: 'Current segment {index}' },
  'editor.emptySegmentHint': { zh: '先输入一行文案。', en: 'Enter one script line first.' },
  'editor.ttsExport': { zh: 'TTS 与导出', en: 'TTS & Export' },
  'editor.ttsEnabled': { zh: '启用 TTS 配音；关闭后按“每句秒数”生成无配音字幕视频', en: 'Enable TTS narration. When disabled, videos use "seconds per segment" without voice.' },
  'editor.ttsEngine': { zh: 'TTS 引擎', en: 'TTS engine' },
  'editor.canvas': { zh: '画布', en: 'Canvas' },
  'editor.width': { zh: '宽度', en: 'Width' },
  'editor.height': { zh: '高度', en: 'Height' },
  'editor.secondsPerSegment': { zh: '每句秒数', en: 'Seconds per segment' },
  'editor.fontPath': { zh: '字体文件路径', en: 'Font file path' },
  'editor.fontPlaceholder': { zh: '留空自动使用系统中文字体', en: 'Leave blank to auto-use a system Chinese font' },
  'editor.currentFont': { zh: '当前字体', en: 'Current font' },
  'editor.backgroundColor': { zh: '背景颜色', en: 'Background color' },
  'editor.generatingButton': { zh: '生成中……', en: 'Generating...' },
  'editor.startGenerate': { zh: '开始生成', en: 'Start generating' },
  'editor.generatedVideo': { zh: '生成视频', en: 'Generated video' },
  'editor.preview': { zh: '预览', en: 'Preview' },
  'editor.videoReady': { zh: '视频已生成', en: 'Video generated' },
  'editor.generating': { zh: '正在生成', en: 'Generating' },
  'editor.waitPlease': { zh: '请稍候', en: 'Please wait' },
  'editor.motionPreview': { zh: '动效预览', en: 'Motion preview' },
  'editor.staticPreview': { zh: '静态预览', en: 'Static preview' },
  'editor.proxyDuration': { zh: '代理时长', en: 'Proxy duration' },
  'editor.notSatisfied': { zh: '不满意，修改', en: 'Not satisfied, edit' },
  'editor.videoGenerating': { zh: '视频生成中……', en: 'Video generating...' },
  'editor.compositing': { zh: '正在合成画面、字幕、配音与音乐', en: 'Compositing visuals, subtitles, voice and music' },
  'editor.backendPreviewAlt': { zh: '后端渲染预览', en: 'Backend-rendered preview' },
  'editor.timelineEmpty': { zh: '文案片段会显示在这里', en: 'Script segments will appear here' },
  'editor.segmentImages': { zh: '片段配图', en: 'Segment images' },
  'editor.eachBlockOneLine': { zh: '每个方块对应一句话', en: 'Each block maps to one line' },
  'editor.segmentBackgroundAlt': { zh: '片段 {index} 背景', en: 'Segment {index} background' },
  'editor.systemSettings': { zh: '系统设置', en: 'System settings' },
  'editor.qwenModelPath': { zh: 'Qwen 模型位置', en: 'Qwen model path' },
  'editor.omniModelPath': { zh: 'OmniVoice 模型位置', en: 'OmniVoice model path' },
  'editor.modelPathPlaceholder': { zh: '留空使用默认位置', en: 'Leave blank to use default path' },
  'editor.notDetected': { zh: '未检测到', en: 'Not detected' },
  'editor.ancientVoice': { zh: '古风参考音色', en: 'Ancient reference voice' },
  'editor.ancientFont': { zh: '古风字体', en: 'Ancient font' },
  'editor.ancientText': { zh: '古风参考文本', en: 'Ancient reference text' },
  'editor.loadingModelStatus': { zh: '正在读取本机模型和 FFmpeg 状态…', en: 'Reading local model and FFmpeg status...' },
  'editor.recheck': { zh: '重新检测', en: 'Recheck' },
  'editor.voicePreset': { zh: '预设语音', en: 'Voice preset' },
  'editor.noVoicePreset': { zh: '不使用预设语音', en: 'Do not use a preset voice' },
  'editor.lineColor': { zh: '行颜色', en: 'Line color' },
  'editor.fontSize': { zh: '字号', en: 'Font size' },
  'editor.captionPosition': { zh: '字幕高低', en: 'Subtitle vertical position' },
  'editor.keyword': { zh: '重点词', en: 'Keyword' },
  'editor.keywordPlaceholder': { zh: '输入当前句中的词', en: 'Enter a word in the current sentence' },
  'editor.mark': { zh: '标记', en: 'Mark' },
  'editor.chooseColor': { zh: '选择颜色 {color}', en: 'Choose color {color}' },
  'editor.qwenCapability': { zh: 'Qwen 能力', en: 'Qwen capability' },
  'editor.presetVoice': { zh: '预设人声', en: 'Preset voice' },
  'editor.voiceDesign': { zh: '语音设计', en: 'Voice design' },
  'editor.voiceClone': { zh: '语音克隆', en: 'Voice clone' },
  'editor.modelSize': { zh: '模型大小', en: 'Model size' },
  'editor.referenceAudioClone': { zh: '克隆参考音频', en: 'Clone reference audio' },
  'editor.referenceAudio': { zh: '参考音频', en: 'Reference audio' },
  'editor.referenceText': { zh: '参考文本', en: 'Reference text' },
  'editor.onlyXVector': { zh: '仅使用 x-vector', en: 'Use x-vector only' },
  'editor.omniMode': { zh: 'OmniVoice 模式', en: 'OmniVoice mode' },
  'editor.autoVoice': { zh: '自动音色', en: 'Auto voice' },
  'editor.speed': { zh: '语速', en: 'Speed' },
  'editor.noDefaultLogic': { zh: '未设置，将使用默认逻辑', en: 'Not set. Default logic will be used.' },
  'editor.bgmLibrary': { zh: 'BGM 音乐库', en: 'BGM library' },
  'editor.noBgmTrack': { zh: '不使用音乐库曲目', en: 'Do not use a library track' },
  'editor.randomBgm': { zh: '随机选一首', en: 'Pick random track' },
  'editor.uploadBgm': { zh: '上传 BGM', en: 'Upload BGM' },
  'editor.randomBgmOnExport': { zh: '导出时随机匹配本地音乐库', en: 'Randomly match the local music library on export' },
  'editor.bgmVolume': { zh: 'BGM 音量', en: 'BGM volume' },
  'editor.currentPath': { zh: '当前：{path}', en: 'Current: {path}' },
  'editor.noBgmLibrary': { zh: '未发现旧项目内置 BGM 库，可上传自己的音乐文件。', en: 'No bundled BGM library found. You can upload your own music file.' },
  'editor.videoGeneration': { zh: '视频生成', en: 'Video generation' },
  'editor.fallbackCaption': { zh: '输入文案，开始创作', en: 'Enter a script to start creating' },
  'error.jobReadFailed': { zh: '任务状态读取失败', en: 'Failed to read job status' },
  'error.systemReadFailed': { zh: '系统状态读取失败', en: 'Failed to read system status' },
  'error.emotionMatchFailed': { zh: '情感模板自动匹配失败', en: 'Emotion template auto-match failed' },
  'error.selectTextToMark': { zh: '请先在文案框中选中要标记的文字', en: 'Select text in the script box before marking it' },
  'error.selectTextToUnmark': { zh: '请先在文案框中选中要取消标记的文字', en: 'Select text in the script box before removing a mark' },
  'error.jobCreateFailed': { zh: '任务创建失败', en: 'Failed to create job' },
  'error.newProjectFailed': { zh: '新建项目失败', en: 'Failed to create new project' },
  'error.localBgmMissing': { zh: '未找到本地 BGM 音乐库', en: 'Local BGM library was not found' },
  'error.wordNotFound': { zh: '当前片段里没有找到“{target}”', en: 'The current segment does not contain "{target}"' },
}

const voicePresetLabels: Dictionary = {
  '男性沧桑旁白': { zh: '男性沧桑旁白', en: 'Male weathered narrator' },
  '男性沉稳': { zh: '男性沉稳', en: 'Male calm' },
  '男性纪录片解说': { zh: '男性纪录片解说', en: 'Male documentary narrator' },
  '男性老夫子': { zh: '男性老夫子', en: 'Male elder scholar' },
  '女性干练': { zh: '女性干练', en: 'Female crisp' },
  '女性缓慢鸡汤': { zh: '女性缓慢鸡汤', en: 'Female slow inspirational' },
  '女性温和主妇': { zh: '女性温和主妇', en: 'Female gentle homemaker' },
  '女性温暖': { zh: '女性温暖', en: 'Female warm' },
}

const exactServerMessages: Dictionary = {
  '项目不存在': { zh: '项目不存在', en: 'Project does not exist' },
  '片段不存在': { zh: '片段不存在', en: 'Segment does not exist' },
  '等待后台 Worker': { zh: '等待后台 Worker', en: 'Waiting for background worker' },
  '任务不存在': { zh: '任务不存在', en: 'Job does not exist' },
  '任务已取消': { zh: '任务已取消', en: 'Job cancelled' },
  '用户已取消': { zh: '用户已取消', en: 'Cancelled by user' },
  '任务失败': { zh: '任务失败', en: 'Job failed' },
  '项目没有可处理的文案片段': { zh: '项目没有可处理的文案片段', en: 'The project has no processable script segments' },
  '项目没有可生成语音的文案': { zh: '项目没有可生成语音的文案', en: 'The project has no script text for voice generation' },
  '项目没有可渲染的文案': { zh: '项目没有可渲染的文案', en: 'The project has no script text to render' },
  '正在准备 TTS': { zh: '正在准备 TTS', en: 'Preparing TTS' },
  '正在保存语音结果': { zh: '正在保存语音结果', en: 'Saving voice results' },
  'TTS 已完成': { zh: 'TTS 已完成', en: 'TTS completed' },
  '正在生成缺失配音': { zh: '正在生成缺失配音', en: 'Generating missing voice lines' },
  '正在准备字幕、配图和音乐': { zh: '正在准备字幕、配图和音乐', en: 'Preparing subtitles, images and music' },
  '正在渲染视频帧与音频': { zh: '正在渲染视频帧与音频', en: 'Rendering video frames and audio' },
  'Worker 已接收任务': { zh: 'Worker 已接收任务', en: 'Worker accepted the job' },
  'Worker 上次退出，任务已标记为可重试': { zh: 'Worker 上次退出，任务已标记为可重试', en: 'The worker exited last time. The job is marked retryable.' },
  '后台 Worker 启动时发现该任务遗留在运行中，请点击重试。': { zh: '后台 Worker 启动时发现该任务遗留在运行中，请点击重试。', en: 'The worker found this job left running from a previous session. Please retry.' },
  '上传文件为空': { zh: '上传文件为空', en: 'Uploaded file is empty' },
  '素材不存在': { zh: '素材不存在', en: 'Asset does not exist' },
  '素材文件不存在': { zh: '素材文件不存在', en: 'Asset file does not exist' },
  'Qwen3-TTS 语音设计模式需要填写声音、情绪或语速描述': { zh: 'Qwen3-TTS 语音设计模式需要填写声音、情绪或语速描述', en: 'Qwen3-TTS voice design mode requires a voice, emotion or speaking-speed description' },
  'Qwen3-TTS 语音克隆需要填写参考文本，或启用仅使用 x-vector': { zh: 'Qwen3-TTS 语音克隆需要填写参考文本，或启用仅使用 x-vector', en: 'Qwen3-TTS voice clone requires reference text, or enable x-vector only' },
  'OmniVoice 语速和步数必须是数字': { zh: 'OmniVoice 语速和步数必须是数字', en: 'OmniVoice speed and steps must be numbers' },
  'OmniVoice 语速建议设置在 0.5 到 2.0 之间': { zh: 'OmniVoice 语速建议设置在 0.5 到 2.0 之间', en: 'OmniVoice speed should be between 0.5 and 2.0' },
  'OmniVoice 步数建议设置在 4 到 64 之间': { zh: 'OmniVoice 步数建议设置在 4 到 64 之间', en: 'OmniVoice steps should be between 4 and 64' },
  'OmniVoice 语音设计模式需要填写语音描述': { zh: 'OmniVoice 语音设计模式需要填写语音描述', en: 'OmniVoice voice design mode requires a voice description' },
  '用户已取消 OmniVoice 生成': { zh: '用户已取消 OmniVoice 生成', en: 'OmniVoice generation was cancelled by the user' },
  '用户已取消 Qwen-TTS 生成': { zh: '用户已取消 Qwen-TTS 生成', en: 'Qwen-TTS generation was cancelled by the user' },
  '未知 OmniVoice 错误': { zh: '未知 OmniVoice 错误', en: 'Unknown OmniVoice error' },
  '未知 Qwen-TTS 错误': { zh: '未知 Qwen-TTS 错误', en: 'Unknown Qwen-TTS error' },
}

const serverPatterns: Array<[RegExp, string]> = [
  [/^当前片段里没有找到“(.+)”$/, 'The current segment does not contain "$1"'],
  [/^字体文件不存在：(.+)$/, 'Font file does not exist: $1'],
  [/^画布参数无效：(.+)$/, 'Invalid canvas parameter: $1'],
  [/^BGM 文件不存在：(.+)$/, 'BGM file does not exist: $1'],
  [/^不支持的 TTS 引擎：(.+)$/, 'Unsupported TTS engine: $1'],
  [/^Qwen3-TTS 模型目录不存在：(.+)$/, 'Qwen3-TTS model directory does not exist: $1'],
  [/^Qwen3-TTS 模型目录不完整：(.+)$/, 'Qwen3-TTS model directory is incomplete: $1'],
  [/^Qwen3-TTS 参考音频不存在：(.+)$/, 'Qwen3-TTS reference audio does not exist: $1'],
  [/^OmniVoice 项目目录不存在：(.+)$/, 'OmniVoice project directory does not exist: $1'],
  [/^OmniVoice 项目目录不完整：(.+)$/, 'OmniVoice project directory is incomplete: $1'],
  [/^OmniVoice 参考音频不存在：(.+)$/, 'OmniVoice reference audio does not exist: $1'],
  [/^OmniVoice Python 不存在：(.+)$/, 'OmniVoice Python does not exist: $1'],
  [/^OmniVoice 后台进程已退出：\n?([\s\S]*)$/, 'OmniVoice background process exited:\n$1'],
  [/^OmniVoice 生成失败：\n?([\s\S]*)$/, 'OmniVoice generation failed:\n$1'],
  [/^OmniVoice 输出文件缺失：\n?([\s\S]*)$/, 'OmniVoice output file is missing:\n$1'],
  [/^预设语音不存在：(.+)$/, 'Preset voice does not exist: $1'],
  [/^视频已生成：(.+)$/, 'Video generated: $1'],
  [/^不支持的文件格式，允许：(.+)$/, 'Unsupported file format. Allowed: $1'],
  [/^暂不支持的任务类型：(.+)$/, 'Unsupported job type: $1'],
  [/^TTS 模型目录不存在：(.+)$/, 'TTS model directory does not exist: $1'],
  [/^Qwen-TTS 后台进程已退出：\n?([\s\S]*)$/, 'Qwen-TTS background process exited:\n$1'],
  [/^Qwen-TTS 生成失败：\n?([\s\S]*)$/, 'Qwen-TTS generation failed:\n$1'],
  [/^TTS 输出文件缺失：\n?([\s\S]*)$/, 'TTS output file is missing:\n$1'],
  [/^找不到模型自带 Python：(.+)$/, 'Cannot find the model-bundled Python: $1'],
  [/^检测到 Windows 版 OmniVoice 模型运行环境，macOS 不能执行 python\.exe。(.+)$/, 'Detected a Windows OmniVoice model runtime. macOS cannot run python.exe. $1'],
  [/^检测到 Windows 版 Qwen3-TTS 模型运行环境，macOS 不能执行 python\.exe。(.+)$/, 'Detected a Windows Qwen3-TTS model runtime. macOS cannot run python.exe. $1'],
  [/^(.+) 副本$/, '$1 copy'],
]

interface I18nContextValue {
  lang: Language
  setLang: (lang: Language) => void
  t: (key: string, values?: Record<string, string | number>) => string
  serverText: (value: string | null | undefined) => string
  voicePresetName: (name: string) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function initialLanguage(): Language {
  const stored = localStorage.getItem(storageKey)
  return stored === 'en' ? 'en' : 'zh'
}

function interpolate(text: string, values?: Record<string, string | number>) {
  if (!values) return text
  return text.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ''))
}

function translateFrom(dict: Dictionary, key: string, lang: Language, values?: Record<string, string | number>) {
  return interpolate(dict[key]?.[lang] ?? key, values)
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(initialLanguage)
  useEffect(() => {
    document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN'
  }, [lang])
  const value = useMemo<I18nContextValue>(() => {
    function setLang(next: Language) {
      localStorage.setItem(storageKey, next)
      document.documentElement.lang = next === 'en' ? 'en' : 'zh-CN'
      setLangState(next)
    }
    function t(key: string, values?: Record<string, string | number>) {
      return translateFrom(dictionary, key, lang, values)
    }
    function serverText(value: string | null | undefined) {
      return translateServerText(value, lang)
    }
    function voicePresetName(name: string) {
      return translateVoicePresetName(name, lang)
    }
    return { lang, setLang, t, serverText, voicePresetName }
  }, [lang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used inside I18nProvider')
  return value
}

export function getStoredLanguage(): Language {
  return localStorage.getItem(storageKey) === 'en' ? 'en' : 'zh'
}

export function translateServerText(value: string | null | undefined, lang: Language) {
  if (!value || lang === 'zh') return value ?? ''
  if (exactServerMessages[value]) return exactServerMessages[value].en
  let result = value
  for (const [pattern, replacement] of serverPatterns) result = result.replace(pattern, replacement)
  return result
}

export function translateVoicePresetName(name: string, lang: Language) {
  return voicePresetLabels[name]?.[lang] ?? name
}

export function LanguageSwitch() {
  const { lang, setLang } = useI18n()
  return <div className="language-switch" aria-label="Language">
    <button type="button" className={lang === 'zh' ? 'active' : ''} onClick={() => setLang('zh')}>中文</button>
    <button type="button" className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
  </div>
}
