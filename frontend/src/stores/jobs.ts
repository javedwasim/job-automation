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

interface JobsState {
  jobs: Job[]
  loading: boolean
  error: string | null
}

export const useJobsStore = defineStore('jobs', {
  state: (): JobsState => ({
    jobs: [],
    loading: false,
    error: null,
  }),
  actions: {
    async fetchJobs() {
      this.loading = true
      this.error = null
      try {
        const { data } = await api.get<Job[]>('/jobs')
        this.jobs = data
      } catch {
        this.error = 'Could not load jobs from the backend.'
      } finally {
        this.loading = false
      }
    },
  },
})
