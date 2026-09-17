import { defineStore } from 'pinia'
import { api } from '../services/api'

export interface ScraperFilters {
  keyword: string
  location: string
  date_posted: string
  job_type: string
  workplace: string
}

export interface ScrapedJob {
  id: number
  source: string
  job_id: string | null
  title: string
  company: string | null
  location: string | null
  posted_text: string | null
  posted_at: string | null
  job_url: string | null
  scraped_at: string
}

export interface ScrapeResult {
  source: string
  search_url: string
  total_found: number
  saved: number
  duplicates: number
  filtered_by_date: number
  errors: number
  jobs: ScrapedJob[]
  scraped_at: string
  message: string | null
}

interface ScraperState {
  filters: ScraperFilters
  loading: boolean
  running: boolean
  result: ScrapeResult | null
  error: string | null
}

export const useScraperStore = defineStore('scraper', {
  state: (): ScraperState => ({
    filters: {
      keyword: '',
      location: '',
      date_posted: 'any',
      job_type: 'any',
      workplace: 'any',
    },
    loading: false,
    running: false,
    result: null,
    error: null,
  }),
  actions: {
    async runScrape() {
      this.running = true
      this.error = null
      this.result = null
      try {
        const { data } = await api.post<ScrapeResult>('/scraper/linkedin/run', this.filters)
        this.result = data
        if (data.message) {
          this.error = data.message
        }
      } catch (err: unknown) {
        const detail = err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
        this.error = detail ?? 'Failed to run the LinkedIn scraper. Is the backend running?'
      } finally {
        this.running = false
      }
    },
    resetFilters() {
      this.filters = {
        keyword: '',
        location: '',
        date_posted: 'any',
        job_type: 'any',
        workplace: 'any',
      }
    },
  },
})
