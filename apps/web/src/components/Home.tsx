import { Copy, Film, FolderOpen, Plus, Trash2 } from 'lucide-react'
import { Brand } from './Brand'
import type { ProjectSummary } from '../types'
interface Props { projects: ProjectSummary[]; loading: boolean; onCreate: () => void; onOpen: (id: string) => void; onDuplicate: (id: string) => void; onDelete: (id: string) => void }
export function Home({ projects, loading, onCreate, onOpen, onDuplicate, onDelete }: Props) {
  return <main className="home">
    <header className="home-header"><Brand /><button className="primary" onClick={onCreate}><Plus size={17}/>新建项目</button></header>
    <section className="home-content"><div className="home-title"><div><h1>最近项目</h1><p>继续创作，或从一段新文案开始。</p></div></div>
      {loading ? <p className="empty">正在读取本地项目…</p> : projects.length === 0 ? <div className="empty-state"><Film size={34}/><h2>创建你的第一条视频</h2><p>输入多行文案，每行都会成为独立片段。</p><button className="primary" onClick={onCreate}><Plus size={17}/>新建空白项目</button></div> :
      <div className="project-list">{projects.map(project => <article className="project-row" key={project.id} onClick={() => onOpen(project.id)}><div className="project-thumb"><Film size={22}/></div><div className="project-meta"><h2>{project.name}</h2><p>{new Date(project.updated_at).toLocaleString('zh-CN')} · {project.template_id}</p></div><button className="icon-button" aria-label="打开项目"><FolderOpen size={18}/></button><button className="icon-button" aria-label="复制项目" onClick={event => { event.stopPropagation(); onDuplicate(project.id) }}><Copy size={18}/></button><button className="icon-button danger" aria-label="删除项目" onClick={event => { event.stopPropagation(); onDelete(project.id) }}><Trash2 size={18}/></button></article>)}</div>}
    </section>
  </main>
}
