import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Check, ChevronDown, Download, Pause, Play, Plus, Settings2, X } from 'lucide-react'
import { api } from '../api'
import { Brand } from './Brand'
import type { Asset, Job, ModelStatus, MusicTrack, Project, SaveState, Segment, VoicePreset } from '../types'
import { applyHighlightSelection, clearHighlights, removeHighlightSelection, syncSegments } from '../features/projects/segments'

interface Props { project: Project; saveState: SaveState; onBack: () => void; onChange: (project: Project) => void; onSaveNow: (project: Project) => Promise<Project>; onCreateNew: () => Promise<Project> }

const saveLabels: Record<SaveState, string> = { saved: '已自动保存', saving: '正在保存…', dirty: '等待保存…', error: '保存失败' }
const commonColors = ['#ffffff', '#f8fafc', '#111827', '#ef4444', '#f97316', '#f59e0b', '#eab308', '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899']
const voiceReferenceText = '你相信吗,一个不会乐器,不会唱歌,甚至五音不全的人今天也能在一分钟内,制作出自己的原创歌曲 '
const fallbackVoicePresets: VoicePreset[] = [
  '男性沧桑旁白',
  '男性沉稳',
  '男性纪录片解说',
  '男性老夫子',
  '女性干练',
  '女性缓慢鸡汤',
  '女性温和主妇',
  '女性温暖',
].map(name => ({
  id: name,
  name,
  path: `storage/resources/voice/${name}.wav`,
  reference_text: voiceReferenceText,
}))

export function Editor({ project, saveState, onBack, onChange, onSaveNow, onCreateNew }: Props) {
  const [activeId, setActiveId] = useState<string | null>(project.segments[0]?.id ?? null)
  const [job, setJob] = useState<Job | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [actionError, setActionError] = useState<string | null>(null)
  const [markText, setMarkText] = useState('')
  const [outputs, setOutputs] = useState<Asset[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null)
  const [bgmTracks, setBgmTracks] = useState<MusicTrack[]>([])
  const [voicePresets, setVoicePresets] = useState<VoicePreset[]>(fallbackVoicePresets)
  const [previewNonce, setPreviewNonce] = useState(() => Date.now())
  const [previewError, setPreviewError] = useState(false)
  const [animatedPreview, setAnimatedPreview] = useState(false)
  const [previewMode, setPreviewMode] = useState<'preview' | 'generating' | 'video'>('preview')
  const refreshedJobs = useRef(new Set<string>())
  const scriptRef = useRef<HTMLTextAreaElement>(null)
  const active = useMemo(() => project.segments.find(segment => segment.id === activeId) ?? project.segments[0], [activeId, project.segments])
  const activeIndex = active ? project.segments.findIndex(segment => segment.id === active.id) : -1
  const script = project.segments.map(segment => segment.text).join('\n')
  const ttsEngine = String(project.tts_settings.engine ?? 'OmniVoice')
  const ttsEnabled = project.tts_settings.enabled !== false
  const renderJob = job?.type === 'render' ? job : jobs.find(item => item.type === 'render' && ['queued', 'running', 'failed', 'cancelled'].includes(item.status))
  const isGenerating = renderJob ? ['queued', 'running'].includes(renderJob.status) : false
  const latestOutput = outputs[0]

  useEffect(() => {
    if (!active && project.segments[0]) setActiveId(project.segments[0].id)
  }, [active, project.segments])

  useEffect(() => {
    if (!job || ['succeeded', 'failed', 'cancelled'].includes(job.status)) return
    const timer = window.setInterval(() => {
      api.getJob(job.id).then(nextJob => {
        setJob(nextJob)
        if (nextJob.status === 'succeeded') {
          refreshAfterJob().then(() => { if (nextJob.type === 'render') setPreviewMode('video') })
        }
        if (['failed', 'cancelled'].includes(nextJob.status) && nextJob.type === 'render') setPreviewMode('preview')
      }).catch(error => setActionError(error instanceof Error ? error.message : '任务状态读取失败'))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [job])

  useEffect(() => {
    api.listJobs(project.id).then(items => {
      items.filter(item => item.status === 'succeeded').forEach(item => refreshedJobs.current.add(item.id))
      setJobs(items)
    }).catch(() => undefined)
    const source = new EventSource(api.jobsEventUrl(project.id))
    source.addEventListener('jobs', event => {
      const nextJobs = JSON.parse((event as MessageEvent).data) as Job[]
      setJobs(nextJobs)
      const finished = nextJobs.find(item => item.status === 'succeeded' && !refreshedJobs.current.has(item.id))
      if (finished) {
        refreshedJobs.current.add(finished.id)
        refreshAfterJob().then(() => { if (finished.type === 'render') setPreviewMode('video') }).catch(() => undefined)
      }
    })
    source.onerror = () => source.close()
    return () => source.close()
  }, [project.id])

  useEffect(() => {
    api.listOutputs(project.id).then(setOutputs).catch(() => undefined)
    api.listBgmTracks().then(setBgmTracks).catch(() => setBgmTracks([]))
    api.listVoicePresets().then(items => setVoicePresets(items.length ? items : fallbackVoicePresets)).catch(() => setVoicePresets(fallbackVoicePresets))
  }, [project.id])

  useEffect(() => {
    setPreviewMode('preview')
    setJob(null)
  }, [project.id])

  useEffect(() => {
    if (saveState === 'saved') {
      setPreviewError(false)
      setAnimatedPreview(false)
      setPreviewNonce(Date.now())
    }
  }, [saveState])

  function updateProject(next: Partial<Project>) {
    onChange({ ...project, ...next })
  }

  function updateActiveSegment(change: Partial<Segment>) {
    if (!active) return
    updateSegment(active.id, change)
  }

  function updateSegment(segmentId: string, change: Partial<Segment>) {
    updateProject({ segments: project.segments.map(segment => segment.id === segmentId ? { ...segment, ...change } : segment) })
  }

  function updateTtsSettings(change: Record<string, unknown>) {
    updateProject({
      tts_settings: { ...project.tts_settings, ...change },
      segments: project.segments.map(segment => ({
        ...segment,
        tts_audio_asset_id: null,
        audio_duration_ms: null,
        status: segment.status === 'audio_ready' ? 'draft' : segment.status,
      })),
    })
  }

  function updateBgmSettings(change: Record<string, unknown>) {
    updateProject({ bgm_settings: { ...project.bgm_settings, ...change } })
  }

  function updateCanvas(change: Partial<Project['canvas']>) {
    updateProject({ canvas: { ...project.canvas, ...change } })
  }

  async function openSettings() {
    setShowSettings(true)
    try {
      setModelStatus(await api.modelStatus())
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '系统状态读取失败')
    }
  }

  async function changeTemplate(templateId: string) {
    if (templateId !== 'ancient-style') {
      const nextProject = {
        ...project,
        template_id: templateId,
        canvas: {
          ...project.canvas,
          caption_position_y: templateId === 'senior-emotion' ? (project.canvas.caption_position_y ?? 0.66) : (project.canvas.caption_position_y ?? 0.5),
          heartbeat_interval_ms: 700,
        },
      }
      onChange(nextProject)
      if (templateId === 'senior-emotion') {
        try {
          setActionError(null)
          await onSaveNow(nextProject)
        } catch (error) {
          setActionError(error instanceof Error ? error.message : '情感模板自动匹配失败')
        }
      }
      return
    }
    const nextProject = {
      ...project,
      template_id: templateId,
      tts_settings: {
        ...project.tts_settings,
        enabled: true,
        engine: 'OmniVoice',
        omnivoice_mode: 'clone',
        omnivoice_ref_audio: modelStatus?.ancient_voice_path ?? project.tts_settings.omnivoice_ref_audio,
        omnivoice_ref_text: modelStatus?.ancient_reference_text ?? project.tts_settings.omnivoice_ref_text,
      },
    }
    onChange(nextProject)
  }

  function addHighlight() {
    if (!active || !markText.trim()) return
    const target = markText.trim()
    const start = active.text.indexOf(target)
    if (start < 0) {
      setActionError(`当前片段里没有找到“${target}”`)
      return
    }
    updateActiveSegment({ marks: [...active.marks, { start, end: start + target.length, text: target, kind: 'highlight' }] })
    setMarkText('')
    setActionError(null)
  }

  function removeHighlight(index: number) {
    if (!active) return
    updateActiveSegment({ marks: active.marks.filter((_, itemIndex) => itemIndex !== index) })
  }

  function addSelectedHighlight() {
    const textarea = scriptRef.current
    if (!textarea || textarea.selectionStart === textarea.selectionEnd) {
      setActionError('请先在文案框中选中要标记的文字')
      return
    }
    updateProject({ segments: applyHighlightSelection(project.segments, textarea.selectionStart, textarea.selectionEnd) })
    setActionError(null)
  }

  function removeSelectedHighlight() {
    const textarea = scriptRef.current
    if (!textarea || textarea.selectionStart === textarea.selectionEnd) {
      setActionError('请先在文案框中选中要取消标记的文字')
      return
    }
    updateProject({ segments: removeHighlightSelection(project.segments, textarea.selectionStart, textarea.selectionEnd) })
    setActionError(null)
  }

  function clearAllHighlights() {
    updateProject({ segments: clearHighlights(project.segments) })
    setActionError(null)
  }

  async function refreshAfterJob() {
    const [freshProject, freshOutputs] = await Promise.all([api.getProject(project.id), api.listOutputs(project.id)])
    onChange(freshProject)
    setOutputs(freshOutputs)
  }

  async function uploadAsset(kind: 'image' | 'reference_audio' | 'bgm', file: File | undefined) {
    if (!file) return null
    setActionError(null)
    try {
      return await api.uploadAsset(kind, file, project.id)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '上传失败')
      return null
    }
  }

  async function uploadReferenceAudio(file: File | undefined) {
    const asset = await uploadAsset('reference_audio', file)
    if (!asset) return
    updateTtsSettings(ttsEngine === 'Qwen3-TTS' ? { qwen_ref_audio: asset.storage_path } : { omnivoice_ref_audio: asset.storage_path })
  }

  async function uploadBgm(file: File | undefined) {
    const asset = await uploadAsset('bgm', file)
    if (asset) updateBgmSettings({ path: asset.storage_path, random: false })
  }

  async function uploadSegmentImage(segmentId: string, file: File | undefined) {
    const asset = await uploadAsset('image', file)
    if (asset) updateSegment(segmentId, {
      background_asset_id: asset.id,
      background_motion: null,
      background_position_x: 0.35 + Math.random() * 0.3,
      background_position_y: 0.35 + Math.random() * 0.3,
    })
  }

  async function enqueueRender() {
    setActionError(null)
    try {
      setPreviewMode('generating')
      setAnimatedPreview(false)
      setPreviewError(false)
      const savedProject = await onSaveNow(project)
      const nextJob = await api.enqueueRender(savedProject.id)
      setJob(nextJob)
      setJobs(current => [nextJob, ...current.filter(item => item.id !== nextJob.id)])
    } catch (error) {
      setPreviewMode('preview')
      setActionError(error instanceof Error ? error.message : '任务创建失败')
    }
  }

  async function createBlankProject() {
    setActionError(null)
    try {
      await onCreateNew()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '新建项目失败')
    }
  }

  async function chooseRandomBgm() {
    setActionError(null)
    try {
      const track = await api.randomBgmTrack()
      updateBgmSettings({ path: track.path, random: true, library_track_id: track.id, mood: track.mood, bpm: track.bpm })
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '未找到本地 BGM 音乐库')
    }
  }

  return <main className="editor">
    <header className="topbar">
      <button className="icon-button" onClick={onBack} aria-label="返回项目"><ArrowLeft size={18}/></button>
      <Brand/>
      <span className={`save-state ${saveState}`}><Check size={14}/>{saveLabels[saveState]}</span>
      <input className="project-name" value={project.name} aria-label="项目名称" onChange={event => updateProject({ name: event.target.value })}/>
      <button className="ghost" onClick={createBlankProject}><Plus size={17}/>新建</button>
      <button className="ghost" onClick={openSettings}><Settings2 size={17}/>设置</button>
    </header>
    <div className="workspace">
      <aside className="script-panel">
        <div className="panel-heading"><div><span>文案</span><small>{project.segments.length} 个片段</small></div></div>
        <textarea ref={scriptRef} aria-label="多行文案" value={script} placeholder={'在这里输入文案\n每个非空行会成为一个片段'} onChange={event => {
          const inputType = (event.nativeEvent as InputEvent).inputType
          const segments = syncSegments(event.target.value, project.segments, inputType === 'insertText' || inputType === 'insertCompositionText')
          updateProject({ segments })
          if (!segments.some(segment => segment.id === activeId)) setActiveId(segments[0]?.id ?? null)
        }}/>
        <div className="script-actions">
          <button type="button" onClick={addSelectedHighlight}>标记重点</button>
          <button type="button" onClick={removeSelectedHighlight}>取消选中标记</button>
          <button type="button" onClick={clearAllHighlights}>清空重点</button>
        </div>
        <div className="segment-stack">{project.segments.map((segment, index) => <button className={segment.id === active?.id ? 'segment active' : 'segment'} key={segment.id} onClick={() => setActiveId(segment.id)}><span>{index + 1}</span><p>{segment.text}</p></button>)}</div>
      </aside>

      <aside className="settings-panel">
        <div className="panel-heading settings-title"><span>模板与画面</span></div>
        <div className="settings-scroll">
          <Setting label="字幕模板"><select value={project.template_id} onChange={event => changeTemplate(event.target.value)}><option value="centered-bold">居中大字</option><option value="scrolling-queue">滚动队列</option><option value="ancient-style">古风模板</option><option value="senior-emotion">情感模板</option></select></Setting>
          <h3>当前片段 {activeIndex >= 0 ? activeIndex + 1 : ''}</h3>
          {active ? <SegmentControls segment={active} markText={markText} setMarkText={setMarkText} addHighlight={addHighlight} removeHighlight={removeHighlight} updateActiveSegment={updateActiveSegment} canvas={project.canvas} updateCanvas={updateCanvas}/> : <p className="inline-hint">先输入一行文案。</p>}
          <h3>TTS 与导出</h3>
          <label className="check-row"><input type="checkbox" checked={ttsEnabled} onChange={event => updateTtsSettings({ enabled: event.target.checked })}/>启用 TTS 配音；关闭后按“每句秒数”生成无配音字幕视频</label>
          <Setting label="TTS 引擎"><select value={ttsEngine} onChange={event => updateTtsSettings({ engine: event.target.value, enabled: true })}><option value="OmniVoice">OmniVoice</option><option value="Qwen3-TTS">Qwen3-TTS</option></select></Setting>
          <VoicePresetSelect presets={voicePresets} value={String(project.tts_settings.voice_preset_id ?? '')} update={updateTtsSettings}/>
          {ttsEngine === 'Qwen3-TTS' ? <QwenSettings settings={project.tts_settings} update={updateTtsSettings} uploadReferenceAudio={uploadReferenceAudio}/> : <OmniSettings settings={project.tts_settings} update={updateTtsSettings} uploadReferenceAudio={uploadReferenceAudio}/>}
          <BgmPanel settings={project.bgm_settings} tracks={bgmTracks} update={updateBgmSettings} uploadBgm={uploadBgm} chooseRandom={chooseRandomBgm}/>
          {actionError && <p className="inline-error">{actionError}</p>}
          <h3>画布</h3>
          <div className="setting-grid"><Setting label="宽度"><input value={project.canvas.width} type="number" min="320" max="3840" onChange={event => updateCanvas({ width: Number(event.target.value) })}/></Setting><Setting label="高度"><input value={project.canvas.height} type="number" min="320" max="4096" onChange={event => updateCanvas({ height: Number(event.target.value) })}/></Setting></div>
          <div className="setting-grid"><Setting label="FPS"><input value={project.canvas.fps ?? 30} type="number" min="1" max="120" onChange={event => updateCanvas({ fps: Number(event.target.value) })}/></Setting><Setting label="每句秒数"><input value={project.canvas.segment_duration ?? 2} type="number" min="0.2" max="60" step="0.1" onChange={event => updateCanvas({ segment_duration: Number(event.target.value) })}/></Setting></div>
          <Setting label="字体文件路径"><input value={project.canvas.font_path ?? ''} placeholder="留空自动使用系统中文字体" onChange={event => updateCanvas({ font_path: event.target.value })}/></Setting>
          <PathBadge label="当前字体" value={project.canvas.font_path ?? ''} clear={() => updateCanvas({ font_path: '' })}/>
          <Setting label="背景颜色"><div className="color-control"><input type="color" value={project.canvas.background_color} onChange={event => updateCanvas({ background_color: event.target.value })}/><code>{project.canvas.background_color}</code></div></Setting>
        </div>
        <div className="generation-footer">
          {renderJob && renderJob.status !== 'succeeded' && <JobDrawer job={renderJob} cancelJob={cancelJob} retryJob={retryJob}/>}
          <button className="primary start-generate" onClick={enqueueRender} disabled={isGenerating}>{isGenerating ? '生成中……' : '开始生成'}</button>
        </div>
      </aside>

      <section className="preview-panel">
        <div className="panel-heading"><span>{previewMode === 'video' && latestOutput ? '生成视频' : '预览'}</span><button className="small-button">9:16 <ChevronDown size={14}/></button></div>
        <PreviewStage project={project} active={active} previewMode={previewMode} latestOutput={latestOutput} animatedPreview={animatedPreview} previewNonce={previewNonce} previewError={previewError} setPreviewError={setPreviewError} setPreviewMode={setPreviewMode} setAnimatedPreview={setAnimatedPreview} setPreviewNonce={setPreviewNonce}/>
        {previewMode === 'video' && latestOutput ? <div className="playbar result-playbar"><span>视频已生成</span><div className="progress"><i style={{ width: '100%' }}/></div><span>{latestOutput.original_name}</span></div> : previewMode === 'generating' ? <div className="playbar generating-playbar"><span>正在生成</span><div className="progress"><i style={{ width: '100%' }}/></div><span>请稍候</span></div> : <div className="playbar"><button className="play" onClick={() => { setPreviewMode('preview'); setPreviewError(false); setAnimatedPreview(value => !value); setPreviewNonce(Date.now()) }}>{animatedPreview ? <Pause size={16} fill="currentColor"/> : <Play size={16} fill="currentColor"/>}</button><span>{animatedPreview ? '动效预览' : '静态预览'}</span><div className="progress"><i style={{ width: animatedPreview ? '100%' : '0%' }}/></div><span>{active?.audio_duration_ms ? `${(active.audio_duration_ms / 1000).toFixed(1)}s` : '代理时长'}</span></div>}
      </section>
    </div>
    <SegmentImageTrack segments={project.segments} activeId={active?.id ?? null} onSelect={setActiveId} uploadSegmentImage={uploadSegmentImage} clearSegmentImage={(segmentId) => updateSegment(segmentId, { background_asset_id: null })}/>
    {showSettings && <SystemPanel status={modelStatus} settings={project.tts_settings} update={updateTtsSettings} close={() => setShowSettings(false)} refresh={openSettings}/>}
  </main>

  async function cancelJob(jobId: string) {
    const currentJob = jobs.find(item => item.id === jobId) ?? job
    const cancelled = await api.cancelJob(jobId)
    setJob(current => current?.id === cancelled.id ? cancelled : current)
    setJobs(current => current.map(item => item.id === cancelled.id ? cancelled : item))
    if (currentJob?.type === 'render') setPreviewMode('preview')
  }

  async function retryJob(jobId: string) {
    setPreviewMode('generating')
    const retried = await api.retryJob(jobId)
    setJob(retried)
    setJobs(current => [retried, ...current])
  }
}

function PreviewStage({ project, active, previewMode, latestOutput, animatedPreview, previewNonce, previewError, setPreviewError, setPreviewMode, setAnimatedPreview, setPreviewNonce }: {
  project: Project
  active: Segment | undefined
  previewMode: 'preview' | 'generating' | 'video'
  latestOutput: Asset | undefined
  animatedPreview: boolean
  previewNonce: number
  previewError: boolean
  setPreviewError: (value: boolean) => void
  setPreviewMode: (value: 'preview' | 'generating' | 'video') => void
  setAnimatedPreview: (value: boolean) => void
  setPreviewNonce: (value: number) => void
}) {
  if (previewMode === 'video' && latestOutput) {
    return <div className="canvas-wrap video-preview-wrap"><div className="video-result-layout"><video className="result-video" src={api.assetContentUrl(latestOutput.id)} controls autoPlay loop/><div className="video-side-actions"><a className="primary" href={api.assetContentUrl(latestOutput.id)} download={latestOutput.original_name}><Download size={15}/>下载</a><button className="ghost" onClick={() => { setPreviewMode('preview'); setPreviewError(false); setAnimatedPreview(false); setPreviewNonce(Date.now()) }}>不满意，修改</button></div></div></div>
  }
  if (previewMode === 'generating') {
    return <div className="canvas-wrap"><div className="canvas generating-canvas"><div className="generating-orb"><i/><i/><i/></div><strong>视频生成中……</strong><p>正在合成画面、字幕、配音与音乐</p></div></div>
  }
  return <div className="canvas-wrap"><div className="canvas" style={previewError ? previewStyle(project, active) : undefined}>{previewError ? <><span className="canvas-grid"/><div className="caption" style={captionFallbackStyle(project, active)}>{renderMarkedText(active)}</div><div className="canvas-signature">AI MEDIA</div></> : <img className="preview-image" src={animatedPreview ? api.previewGifUrl(project.id, active?.id, previewNonce) : api.previewUrl(project.id, active?.id, previewNonce)} alt="后端渲染预览" onLoad={() => { if (previewMode === 'preview') setPreviewMode('preview') }} onError={() => setPreviewError(true)}/>}</div></div>
}

function SegmentImageTrack({ segments, activeId, onSelect, uploadSegmentImage, clearSegmentImage }: {
  segments: Segment[]
  activeId: string | null
  onSelect: (id: string) => void
  uploadSegmentImage: (segmentId: string, file: File | undefined) => Promise<void>
  clearSegmentImage: (segmentId: string) => void
}) {
  if (!segments.length) return <footer className="timeline"><div className="timeline-empty">文案片段会显示在这里</div></footer>
  return <footer className="timeline"><div className="timeline-head"><strong>片段配图</strong><span>每个方块对应一句话</span></div><div className="timeline-items">{segments.map((segment, index) => <div className={segment.id === activeId ? 'timeline-item image active' : 'timeline-item image'} key={segment.id} onClick={() => onSelect(segment.id)}><span>{index + 1}</span><div className="track-thumb">{segment.background_asset_id ? <img src={api.assetContentUrl(segment.background_asset_id)} alt={`片段 ${index + 1} 背景`}/> : <strong>+</strong>}</div><div className="track-actions" onClick={event => event.stopPropagation()}><label>{segment.background_asset_id ? '修改' : '上传'}<input type="file" accept=".png,.jpg,.jpeg,.webp,image/*" onChange={event => uploadSegmentImage(segment.id, event.target.files?.[0])}/></label>{segment.background_asset_id && <button type="button" onClick={() => clearSegmentImage(segment.id)}>删除</button>}</div></div>)}</div></footer>
}

function SystemPanel({ status, settings, update, close, refresh }: { status: ModelStatus | null; settings: Record<string, unknown>; update: (change: Record<string, unknown>) => void; close: () => void; refresh: () => void }) {
  return <div className="modal-backdrop"><section className="system-panel"><div className="panel-heading"><span>系统设置</span><button className="icon-button" onClick={close}><X size={16}/></button></div>
    <div className="system-settings">
      <Setting label="Qwen 模型位置"><input value={String(settings.qwen_model_dir ?? '')} placeholder={status?.qwen_model_dir || '留空使用默认位置'} onChange={event => update({ qwen_model_dir: event.target.value })}/></Setting>
      <Setting label="OmniVoice 模型位置"><input value={String(settings.omnivoice_project_dir ?? '')} placeholder={status?.omnivoice_project_dir || '留空使用默认位置'} onChange={event => update({ omnivoice_project_dir: event.target.value })}/></Setting>
    </div>
    {status ? <div className="status-grid"><StatusItem label="Qwen3-TTS" ok={status.qwen_available} detail={status.qwen_model_dir}/><StatusItem label="Qwen Python" ok={status.qwen_available} detail={status.qwen_python}/><StatusItem label="OmniVoice" ok={status.omnivoice_available} detail={status.omnivoice_project_dir}/><StatusItem label="Omni Python" ok={status.omnivoice_available} detail={status.omnivoice_python}/><StatusItem label="FFmpeg" ok={status.ffmpeg_available} detail={status.ffmpeg_path || '未检测到'}/><StatusItem label="古风参考音色" ok={status.ancient_voice_available} detail={status.ancient_voice_path}/><StatusItem label="古风字体" ok={status.ancient_font_available} detail={status.ancient_font_path}/><div className="status-item wide"><strong>古风参考文本</strong><p>{status.ancient_reference_text}</p></div></div> : <p className="inline-hint">正在读取本机模型和 FFmpeg 状态…</p>}<button className="wide-control" onClick={refresh}>重新检测<span>本机</span></button></section></div>
}

function StatusItem({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return <div className={ok ? 'status-item ok' : 'status-item bad'}><strong>{label}</strong><span>{ok ? '可用' : '不可用'}</span><p>{detail}</p></div>
}

function VoicePresetSelect({ presets, value, update }: { presets: VoicePreset[]; value: string; update: (change: Record<string, unknown>) => void }) {
  return <Setting label="预设语音"><select value={value} onChange={event => update({
    voice_preset_id: event.target.value,
    qwen_mode: event.target.value ? 'voice_clone' : undefined,
    omnivoice_mode: event.target.value ? 'clone' : undefined,
    qwen_use_xvector_only: false,
  })}>
    <option value="">不使用预设语音</option>
    {presets.map(preset => <option value={preset.id} key={preset.id}>{preset.name}</option>)}
  </select></Setting>
}

function SegmentControls({ segment, markText, setMarkText, addHighlight, removeHighlight, updateActiveSegment, canvas, updateCanvas }: {
  segment: Segment
  markText: string
  setMarkText: (value: string) => void
  addHighlight: () => void
  removeHighlight: (index: number) => void
  updateActiveSegment: (change: Partial<Segment>) => void
  canvas: Project['canvas']
  updateCanvas: (change: Partial<Project['canvas']>) => void
}) {
  const [colorOpen, setColorOpen] = useState(false)
  const currentColor = segment.text_color ?? '#ffffff'
  return <>
    <Setting label="行颜色"><ColorPicker value={currentColor} isDefault={!segment.text_color} open={colorOpen} setOpen={setColorOpen} update={color => updateActiveSegment({ text_color: color })} clear={() => updateActiveSegment({ text_color: null })}/></Setting>
    <div className="setting-grid"><Setting label="字号"><input value={canvas.font_size ?? 108} type="number" min="20" max="260" onChange={event => updateCanvas({ font_size: Number(event.target.value) })}/></Setting><Setting label="字幕高低"><input value={Math.round((canvas.caption_position_y ?? 0.5) * 100)} type="number" min="5" max="95" onChange={event => updateCanvas({ caption_position_y: Number(event.target.value) / 100 })}/></Setting></div>
    <Setting label="重点词"><div className="inline-edit"><input value={markText} placeholder="输入当前句中的词" onChange={event => setMarkText(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') addHighlight() }}/><button type="button" onClick={addHighlight}>标记</button></div></Setting>
    <div className="mark-list">{segment.marks.map((mark, index) => <button key={`${mark.text}-${index}`} onClick={() => removeHighlight(index)}><span>{String(mark.text)}</span><X size={12}/></button>)}</div>
  </>
}

function ColorPicker({ value, isDefault, open, setOpen, update, clear }: {
  value: string
  isDefault: boolean
  open: boolean
  setOpen: (open: boolean) => void
  update: (color: string) => void
  clear: () => void
}) {
  return <div className="color-picker">
    <button className="color-trigger" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span style={{ background: value }}/>
      <code>{isDefault ? '默认' : value}</code>
    </button>
    {open && <div className="color-popover">
      <div className="color-popover-head">
        <input type="color" value={value} onChange={event => update(event.target.value)}/>
        <code>{value}</code>
        <button type="button" onClick={() => { clear(); setOpen(false) }}>默认</button>
      </div>
      <div className="color-swatches">{commonColors.map(color => <button type="button" key={color} aria-label={`选择颜色 ${color}`} style={{ background: color }} onClick={() => { update(color); setOpen(false) }}/>)}</div>
    </div>}
  </div>
}

function QwenSettings({ settings, update, uploadReferenceAudio }: SettingsProps) {
  const mode = String(settings.qwen_mode ?? 'preset')
  const usingPreset = Boolean(settings.voice_preset_id)
  return <>
    <Setting label="Qwen 能力"><select value={mode} onChange={event => update({ qwen_mode: event.target.value })}><option value="preset">预设人声</option><option value="voice_design">语音设计</option><option value="voice_clone">语音克隆</option></select></Setting>
    {mode === 'preset' && <Setting label="预设人声"><input value={String(settings.qwen_speaker ?? 'Vivian')} onChange={event => update({ qwen_speaker: event.target.value })}/></Setting>}
    <div className="setting-grid"><Setting label="语言"><input value={String(settings.qwen_language ?? 'Chinese')} onChange={event => update({ qwen_language: event.target.value })}/></Setting><Setting label="模型大小"><select value={String(settings.qwen_model_size ?? '1.7B')} onChange={event => update({ qwen_model_size: event.target.value })}><option value="1.7B">1.7B</option><option value="0.6B">0.6B</option></select></Setting></div>
    {mode === 'voice_design' && <Setting label="语音设计"><textarea value={String(settings.qwen_instruct ?? '')} onChange={event => update({ qwen_instruct: event.target.value })}/></Setting>}
    {mode === 'voice_clone' && !usingPreset && <>
      <AudioUploadSetting label="克隆参考音频" value={String(settings.qwen_ref_audio ?? '')} upload={uploadReferenceAudio} clear={() => update({ qwen_ref_audio: '' })}/>
      <Setting label="参考文本"><textarea value={String(settings.qwen_ref_text ?? '')} onChange={event => update({ qwen_ref_text: event.target.value })}/></Setting>
      <label className="check-row"><input type="checkbox" checked={Boolean(settings.qwen_use_xvector_only)} onChange={event => update({ qwen_use_xvector_only: event.target.checked })}/>仅使用 x-vector</label>
    </>}
  </>
}

function OmniSettings({ settings, update, uploadReferenceAudio }: SettingsProps) {
  const mode = String(settings.omnivoice_mode ?? 'auto')
  const usingPreset = Boolean(settings.voice_preset_id)
  return <>
    <Setting label="OmniVoice 模式"><select value={mode} onChange={event => update({ omnivoice_mode: event.target.value })}><option value="auto">自动音色</option><option value="design">语音设计</option><option value="clone">语音克隆</option></select></Setting>
    <Setting label="语速"><input type="number" step="0.1" min="0.5" max="2" value={String(settings.omnivoice_speed ?? 1)} onChange={event => update({ omnivoice_speed: Number(event.target.value) })}/></Setting>
    {mode === 'clone' && !usingPreset && <>
      <AudioUploadSetting label="参考音频" value={String(settings.omnivoice_ref_audio ?? '')} upload={uploadReferenceAudio} clear={() => update({ omnivoice_ref_audio: '' })}/>
      <Setting label="参考文本"><textarea value={String(settings.omnivoice_ref_text ?? '')} onChange={event => update({ omnivoice_ref_text: event.target.value })}/></Setting>
    </>}
    {mode === 'design' && <Setting label="语音设计"><textarea value={String(settings.omnivoice_instruct ?? 'female, natural, clear')} onChange={event => update({ omnivoice_instruct: event.target.value })}/></Setting>}
  </>
}

function AudioUploadSetting({ label, value, upload, clear }: { label: string; value: string; upload: (file: File | undefined) => Promise<void>; clear: () => void }) {
  return <div className="audio-upload"><span>{label}</span><label>{value ? '修改文件' : '选择文件'}<input type="file" accept=".wav,.mp3,.m4a,.flac,audio/*" onChange={event => upload(event.target.files?.[0])}/></label>{value ? <><code title={value}>{value}</code><button type="button" onClick={clear}>清除</button></> : <small>未设置</small>}</div>
}

function PathBadge({ label, value, clear }: { label: string; value: string; clear: () => void }) {
  return <div className="path-badge"><span>{label}</span>{value ? <><code title={value}>{value}</code><button type="button" onClick={clear}>清除</button></> : <small>未设置，将使用默认逻辑</small>}</div>
}

function BgmPanel({ settings, tracks, update, uploadBgm, chooseRandom }: {
  settings: Record<string, unknown>
  tracks: MusicTrack[]
  update: (change: Record<string, unknown>) => void
  uploadBgm: (file: File | undefined) => Promise<void>
  chooseRandom: () => Promise<void>
}) {
  const selectedPath = String(settings.path ?? '')
  return <>
    <Setting label="BGM 音乐库">
      <select value={selectedPath} onChange={event => {
        const track = tracks.find(item => item.path === event.target.value)
        update({ path: event.target.value, random: false, library_track_id: track?.id ?? '', mood: track?.mood ?? '', bpm: track?.bpm ?? null, beat_sync: false })
      }}>
        <option value="">不使用音乐库曲目</option>
        {tracks.map(track => <option value={track.path} key={track.id}>{track.name} · {track.mood}</option>)}
      </select>
    </Setting>
    <div className="bgm-actions">
      <button type="button" onClick={chooseRandom}>随机选一首</button>
      <label><span>上传 BGM</span><input type="file" accept=".mp3,.wav,.m4a,.flac,audio/*" onChange={event => uploadBgm(event.target.files?.[0])}/></label>
    </div>
    <label className="check-row"><input type="checkbox" checked={Boolean(settings.random)} onChange={event => update({ random: event.target.checked })}/>导出时随机匹配本地音乐库</label>
    <Setting label="BGM 音量"><div className="range-control"><input type="range" min="0" max="1" step="0.01" value={Number(settings.volume ?? 0.3)} onChange={event => update({ volume: Number(event.target.value) })}/><span>{Math.round(Number(settings.volume ?? 0.3) * 100)}%</span></div></Setting>
    {selectedPath && <p className="bgm-current">当前：{selectedPath}</p>}
    {!tracks.length && <p className="inline-hint">未发现旧项目内置 BGM 库，可上传自己的音乐文件。</p>}
  </>
}

interface SettingsProps {
  settings: Record<string, unknown>
  update: (change: Record<string, unknown>) => void
  uploadReferenceAudio: (file: File | undefined) => Promise<void>
}

function JobDrawer({ job, cancelJob, retryJob }: { job: Job; cancelJob: (id: string) => void; retryJob: (id: string) => void }) {
  const isActive = ['queued', 'running'].includes(job.status)
  return <div className={`job-drawer ${job.status}`}>
    <div className="job-drawer-head"><strong>视频生成</strong><small>{job.status} · {Math.round(job.progress)}%</small></div>
    <p>{job.stage}</p>
    <div className="job-progress"><i style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}/></div>
    {job.error_message && <pre>{job.error_message}</pre>}
    <div className="job-drawer-actions">{isActive && <button type="button" onClick={() => cancelJob(job.id)}>取消</button>}{['failed', 'cancelled'].includes(job.status) && <button type="button" onClick={() => retryJob(job.id)}>重试</button>}</div>
  </div>
}

function Setting({ label, children }: { label: string; children: React.ReactNode }) { return <label className="setting"><span>{label}</span>{children}</label> }

function renderMarkedText(segment: Segment | undefined) {
  if (!segment) return '输入文案，开始创作'
  if (!segment.marks.length) return segment.text
  const parts: React.ReactNode[] = []
  let cursor = 0
  const marks = [...segment.marks].sort((a, b) => Number(a.start) - Number(b.start))
  marks.forEach((mark, index) => {
    const start = Math.max(cursor, Number(mark.start))
    const end = Math.min(segment.text.length, Number(mark.end))
    if (start > cursor) parts.push(segment.text.slice(cursor, start))
    if (end > start) parts.push(<mark key={`${start}-${end}-${index}`}>{segment.text.slice(start, end)}</mark>)
    cursor = Math.max(cursor, end)
  })
  if (cursor < segment.text.length) parts.push(segment.text.slice(cursor))
  return parts
}

function previewStyle(project: Project, segment: Segment | undefined): React.CSSProperties {
  const style: React.CSSProperties = { background: project.canvas.background_color }
  if (segment?.background_asset_id) {
    style.backgroundImage = `linear-gradient(#0009,#0009), url("${api.assetContentUrl(segment.background_asset_id)}")`
    style.backgroundSize = 'cover'
    style.backgroundPosition = `${segment.background_position_x * 100}% ${segment.background_position_y * 100}%`
  }
  return style
}

function captionFallbackStyle(project: Project, segment: Segment | undefined): React.CSSProperties {
  const position = Math.max(0.05, Math.min(0.95, project.canvas.caption_position_y ?? (project.template_id === 'senior-emotion' ? 0.66 : 0.5)))
  return {
    color: segment?.text_color ?? undefined,
    top: `${position * 100}%`,
    bottom: 'auto',
    transform: 'translateY(-50%)',
  }
}
