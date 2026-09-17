import { defineStore } from 'pinia'
import { api } from '../services/api'

export interface Job {
  id: number
  title: string
  company: string | null
  location: string | null
  source: string | null
  job_url: string | null
  application_url: string | null
  categories: string[]
  job_posted_at: string | null
  received_at: string
  status: string
}

// Visited-link tracking (localStorage, per browser) so the dashboard can
// mark job links the user has already opened. Keyed by URL: two rows
// pointing at the same link are both "visited".
const VISITED_STORAGE_KEY = 'job-automation:visited-job-urls'
const MAX_VISITED_URLS = 1000

function loadVisitedUrls(): Set<string> {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(VISITED_STORAGE_KEY)
    if (!raw) return new Set()
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((value): value is string => typeof value === 'string'))
  } catch {
    // Corrupted or unavailable localStorage — start fresh rather than crash.
    return new Set()
  }
}

function persistVisitedUrls(urls: Set<string>): void {
  if (typeof window === 'undefined') return
  try {
    // Keep only the most recent MAX_VISITED_URLS entries to bound growth
    // (Set preserves insertion order, so the oldest keys drop off first).
    const trimmed = [...urls].slice(-MAX_VISITED_URLS)
    window.localStorage.setItem(VISITED_STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // Private mode / quota exceeded — tracking simply won't persist.
  }
}

interface JobsPage {
  items: Job[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

interface JobsState {
  jobs: Job[]
  loading: boolean
  error: string | null
  visitedUrls: Set<string>
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export const useJobsStore = defineStore('jobs', {
  state: (): JobsState => ({
    jobs: [],
    loading: false,
    error: null,
    visitedUrls: loadVisitedUrls(),
    total: 0,
    page: 1,
    pageSize: 20,
    totalPages: 0,
  }),
  actions: {
    async fetchJobs(page?: number) {
      const targetPage = page ?? this.page
      this.loading = true
      this.error = null
      try {
        const { data } = await api.get<JobsPage>('/jobs', {
          params: { page: targetPage, page_size: this.pageSize },
        })
        this.jobs = data.items
        this.total = data.total
        this.page = data.page
        this.totalPages = data.total_pages
      } catch {
        this.error = 'Could not load jobs from the backend.'
      } finally {
        this.loading = false
      }
    },
    async goToPage(page: number) {
      if (page < 1 || page > this.totalPages || page === this.page || this.loading) return
      await this.fetchJobs(page)
    },
    markVisited(url: string | null) {
      if (!url) return
      this.visitedUrls.add(url)
      persistVisitedUrls(this.visitedUrls)
    },
    isVisited(url: string | null): boolean {
      return url !== null && this.visitedUrls.has(url)
    },
  },
})
