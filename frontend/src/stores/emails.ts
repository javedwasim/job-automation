import { defineStore } from 'pinia'
import { api } from '../services/api'

export interface JobEmail {
  id: number
  gmail_message_id: string
  source: string | null
  sender: string
  subject: string
  received_at: string
  status: string
}

interface SyncResult {
  account_email: string
  messages_found: number
  messages_ingested: number
  messages_skipped_duplicate: number
  messages_failed: number
}

interface GmailAccount {
  id: number
  email: string
  connected_at: string
  token_expires_at: string
}

interface EmailsState {
  emails: JobEmail[]
  accounts: GmailAccount[]
  loading: boolean
  syncing: boolean
  backfilling: boolean
  error: string | null
  lastSyncResults: SyncResult[]
}

export const useEmailsStore = defineStore('emails', {
  state: (): EmailsState => ({
    emails: [],
    accounts: [],
    loading: false,
    syncing: false,
    backfilling: false,
    error: null,
    lastSyncResults: [],
  }),
  actions: {
    async fetchAccounts() {
      try {
        const { data } = await api.get<GmailAccount[]>('/gmail/accounts')
        this.accounts = data
      } catch {
        // Non-fatal — the dashboard just shows "no account connected".
      }
    },
    async fetchEmails() {
      this.loading = true
      this.error = null
      try {
        const { data } = await api.get<JobEmail[]>('/gmail/emails')
        this.emails = data
      } catch {
        this.error = 'Could not load emails from the backend.'
      } finally {
        this.loading = false
      }
    },
    async syncNow() {
      this.syncing = true
      this.error = null
      try {
        const { data } = await api.post<SyncResult[]>('/gmail/sync')
        this.lastSyncResults = data
        await this.fetchEmails()
      } catch {
        this.error = 'Sync failed. Is a Gmail account connected?'
      } finally {
        this.syncing = false
      }
    },
    async backfillJobs() {
      this.backfilling = true
      this.error = null
      try {
        await api.post('/gmail/backfill')
      } catch {
        this.error = 'Backfill failed.'
      } finally {
        this.backfilling = false
      }
    },
  },
})
