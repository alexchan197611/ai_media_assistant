import { Copy, Film, FolderOpen, Plus, Trash2 } from 'lucide-react'
import { Brand } from './Brand'
import { LanguageSwitch, useI18n } from '../i18n'
import type { ProjectSummary } from '../types'
interface Props { projects: ProjectSummary[]; loading: boolean; onCreate: () => void; onOpen: (id: string) => void; onDuplicate: (id: string) => void; onDelete: (id: string) => void }
export function Home({ projects, loading, onCreate, onOpen, onDuplicate, onDelete }: Props) {
  const { lang, t } = useI18n()
  return <main className="home">
    <header className="home-header"><Brand /><div className="home-actions"><LanguageSwitch/><button className="primary" onClick={onCreate}><Plus size={17}/>{t('home.newProject')}</button></div></header>
    <section className="home-content"><div className="home-title"><div><h1>{t('home.recentProjects')}</h1><p>{t('home.subtitle')}</p></div></div>
      {loading ? <p className="empty">{t('home.loading')}</p> : projects.length === 0 ? <div className="empty-state"><Film size={34}/><h2>{t('home.emptyTitle')}</h2><p>{t('home.emptyBody')}</p><button className="primary" onClick={onCreate}><Plus size={17}/>{t('home.newBlankProject')}</button></div> :
      <div className="project-list">{projects.map(project => <article className="project-row" key={project.id} onClick={() => onOpen(project.id)}><div className="project-thumb"><Film size={22}/></div><div className="project-meta"><h2>{project.name}</h2><p>{new Date(project.updated_at).toLocaleString(lang === 'en' ? 'en-US' : 'zh-CN')} · {project.template_id}</p></div><button className="icon-button" aria-label={t('home.openProject')}><FolderOpen size={18}/></button><button className="icon-button" aria-label={t('home.duplicateProject')} onClick={event => { event.stopPropagation(); onDuplicate(project.id) }}><Copy size={18}/></button><button className="icon-button danger" aria-label={t('home.deleteProject')} onClick={event => { event.stopPropagation(); onDelete(project.id) }}><Trash2 size={18}/></button></article>)}</div>}
    </section>
  </main>
}
