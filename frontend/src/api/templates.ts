import { apiGet } from './client'
import type { ScorerTemplate } from '../types'

export const listTemplates = () => apiGet<ScorerTemplate[]>('/scorer-templates')
