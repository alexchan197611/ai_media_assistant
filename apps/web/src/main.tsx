import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { I18nProvider } from './i18n'
import './styles.css'
const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } })
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={queryClient}><I18nProvider><App/></I18nProvider></QueryClientProvider></StrictMode>)
