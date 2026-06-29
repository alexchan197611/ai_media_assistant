import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { Editor } from './components/Editor'
import { Home } from './components/Home'
import { useI18n } from './i18n'
import type { Project, SaveState } from './types'

export default function App() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [projectId, setProjectId] = useState<string | null>(() => new URLSearchParams(location.search).get('project'))
  const [draft, setDraft] = useState<Project | null>(null)
  const [saveState, setSaveState] = useState<SaveState>('saved')
  const hydratedId = useRef<string | null>(null)
  const latestDraft = useRef<Project | null>(null)
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.listProjects })
  const project = useQuery({ queryKey: ['project', projectId], queryFn: () => api.getProject(projectId!), enabled: Boolean(projectId) })
  useEffect(() => { if (project.data && hydratedId.current !== project.data.id) { setDraft(project.data); latestDraft.current = project.data; hydratedId.current = project.data.id } }, [project.data])
  const create = useMutation({ mutationFn: () => api.createProject(t('app.untitled')), onSuccess: value => openProject(value.id) })
  const duplicate = useMutation({ mutationFn: api.duplicateProject, onSuccess: value => { queryClient.invalidateQueries({ queryKey: ['projects'] }); openProject(value.id) } })
  const remove = useMutation({ mutationFn: api.deleteProject, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }) })
  const save = useMutation({ mutationFn: api.updateProject, onMutate: () => setSaveState('saving'), onSuccess: (saved, submitted) => {
    const currentMatchesSubmitted = JSON.stringify(latestDraft.current) === JSON.stringify(submitted)
    if (currentMatchesSubmitted) {
      latestDraft.current = saved
      setDraft(saved)
    }
    setSaveState(currentMatchesSubmitted ? 'saved' : 'dirty')
    queryClient.setQueryData(['project', saved.id], saved)
    queryClient.invalidateQueries({ queryKey: ['projects'] })
  }, onError: () => setSaveState('error') })
  useEffect(() => { if (!draft || saveState !== 'dirty') return; const timer = window.setTimeout(() => save.mutate(draft), 800); return () => clearTimeout(timer) }, [draft, saveState])
  function openProject(id: string | null) { setProjectId(id); hydratedId.current = null; history.pushState({}, '', id ? `?project=${id}` : location.pathname) }
  function changeDraft(next: Project) { latestDraft.current = next; setDraft(next); setSaveState('dirty') }
  async function createNewProject() {
    const project = await api.createProject(t('app.untitled'))
    queryClient.invalidateQueries({ queryKey: ['projects'] })
    openProject(project.id)
    return project
  }
  async function saveDraftNow(next: Project) {
    latestDraft.current = next
    setSaveState('saving')
    try {
      const saved = await api.updateProject(next)
      latestDraft.current = saved
      setDraft(saved)
      setSaveState('saved')
      queryClient.setQueryData(['project', saved.id], saved)
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      return saved
    } catch (error) {
      setSaveState('error')
      throw error
    }
  }
  if (projectId) {
    if (project.isError) return <div className="fatal">{t('app.loadFailed')}<button onClick={() => openProject(null)}>{t('app.backHome')}</button></div>
    if (!draft) return <div className="loading">{t('app.openingEditor')}</div>
    return <Editor project={draft} saveState={saveState} onBack={() => openProject(null)} onChange={changeDraft} onSaveNow={saveDraftNow} onCreateNew={createNewProject}/>
  }
  return <Home projects={projects.data ?? []} loading={projects.isLoading} onCreate={() => create.mutate()} onOpen={openProject} onDuplicate={id => duplicate.mutate(id)} onDelete={id => { if (confirm(t('app.deleteConfirm'))) remove.mutate(id) }}/>
}
