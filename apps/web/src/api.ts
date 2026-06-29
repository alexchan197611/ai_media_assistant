import type { Asset, Job, ModelStatus, MusicTrack, Project, ProjectSummary, VoicePreset, WorkerStatus } from './types'
import { getStoredLanguage } from './i18n'
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json', 'Accept-Language': getStoredLanguage() }, ...init })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? (getStoredLanguage() === 'en' ? 'Request failed' : '请求失败'))
  return response.status === 204 ? undefined as T : response.json()
}
async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`/api${path}`, { method: 'POST', headers: { 'Accept-Language': getStoredLanguage() }, body: form })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? (getStoredLanguage() === 'en' ? 'Upload failed' : '上传失败'))
  return response.json()
}
export const api = {
  listProjects: () => request<ProjectSummary[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (name = getStoredLanguage() === 'en' ? 'Untitled video' : '未命名项目') => request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, segments: [] }) }),
  updateProject: (project: Project) => request<Project>(`/projects/${project.id}`, { method: 'PATCH', body: JSON.stringify({ name: project.name, canvas: project.canvas, template_id: project.template_id, tts_settings: project.tts_settings, bgm_settings: project.bgm_settings, segments: project.segments }) }),
  duplicateProject: (id: string) => request<Project>(`/projects/${id}/duplicate`, { method: 'POST' }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  modelStatus: () => request<ModelStatus>('/models/status'),
  enqueueTts: (projectId: string) => request<Job>(`/projects/${projectId}/tts/all`, { method: 'POST' }),
  enqueueSegmentTts: (projectId: string, segmentId: string) => request<Job>(`/projects/${projectId}/tts/segments/${segmentId}`, { method: 'POST' }),
  enqueueRender: (projectId: string) => request<Job>(`/projects/${projectId}/render`, { method: 'POST' }),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  listJobs: (projectId: string) => request<Job[]>(`/jobs?project_id=${projectId}`),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }),
  retryJob: (id: string) => request<Job>(`/jobs/${id}/retry`, { method: 'POST' }),
  workerStatus: () => request<WorkerStatus>('/jobs/worker/status'),
  listBgmTracks: () => request<MusicTrack[]>('/bgm/tracks'),
  randomBgmTrack: () => request<MusicTrack>('/bgm/random'),
  listVoicePresets: () => request<VoicePreset[]>('/voice/presets'),
  jobsEventUrl: (projectId: string) => `/api/jobs/events/stream?project_id=${projectId}`,
  listOutputs: (projectId: string) => request<Asset[]>(`/projects/${projectId}/outputs`),
  uploadAsset: (kind: 'image' | 'reference_audio' | 'bgm', file: File, projectId?: string) => upload<Asset>(`/assets?${new URLSearchParams({ kind, ...(projectId ? { project_id: projectId } : {}) })}`, file),
  assetContentUrl: (id: string) => `/api/assets/${id}/content`,
  previewUrl: (projectId: string, segmentId: string | undefined, nonce: number) => `/api/projects/${projectId}/preview.png?${new URLSearchParams({ ...(segmentId ? { segment_id: segmentId } : {}), v: String(nonce) })}`,
  previewGifUrl: (projectId: string, segmentId: string | undefined, nonce: number) => `/api/projects/${projectId}/preview.gif?${new URLSearchParams({ ...(segmentId ? { segment_id: segmentId } : {}), v: String(nonce) })}`,
}
