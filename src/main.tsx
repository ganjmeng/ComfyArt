import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { BRAND } from './brand'
import { initLocale } from './i18n'
import './styles/base.css'
import './styles/canvas.css'
import './styles/shell.css'
import './styles/overlays.css'

await initLocale()
await (await import('./theme')).initTheme()
document.title = BRAND.pageTitle

const params = new URL(location.href).searchParams
const project = params.get('project')
const root = createRoot(document.getElementById('root')!)
const { NEW_PARAM, projectExists } = await import('./projects')

if (project && (params.has(NEW_PARAM) || await projectExists(project))) {
  const { mountCanvasLoader } = await import('./loomiLoader')
  const loader = await mountCanvasLoader()
  const { App } = await import('./App')
  root.render(<StrictMode><App id={project} onCanvasReady={() => loader.ready()} /></StrictMode>)
} else {
  const { HomeApp } = await import('./home/HomeApp')
  const viewParam = params.get('view')
  const homeView = viewParam === 'projects' || viewParam === 'skills' || viewParam === 'schedules' || viewParam === 'arti' ? viewParam : 'home'
  root.render(<StrictMode><HomeApp view={project ? { missing: project } : homeView} /></StrictMode>)
}
