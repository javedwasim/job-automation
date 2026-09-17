import { defineStore } from 'pinia'
import { api } from '../services/api'

interface OverviewState {
  status: 'idle' | 'loading' | 'ready' | 'error'
  backendStatus: string | null
}

export const useOverviewStore = defineStore('overview', {
  state: (): OverviewState => ({
    status: 'idle',
    backendStatus: null,
  }),
  actions: {
    async checkBackend() {
      this.status = 'loading'
      try {
        const { data } = await api.get('/health')
        this.backendStatus = data.status
        this.status = 'ready'
      } catch {
        this.status = 'error'
      }
    },
  },
})
