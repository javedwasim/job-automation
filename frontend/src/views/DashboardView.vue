<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useOverviewStore } from '../stores/overview'
import { useEmailsStore } from '../stores/emails'
import { useJobsStore } from '../stores/jobs'
import { api } from '../services/api'

const router = useRouter()
const overview = useOverviewStore()
const emails = useEmailsStore()
const jobs = useJobsStore()

const connectedAccount = computed(() => emails.accounts[0] ?? null)

onMounted(async () => {
  overview.checkBackend()
  jobs.fetchJobs()

  // Check if we're coming back from Google's OAuth redirect (Google -> backend callback -> browser redirect back here)
  // The backend returns a 200 response (browser receives HTML), but we can still fetch accounts to check if a new one was added
  const params = new URLSearchParams(window.location.search)
  const error = params.get('error')

  if (error) {
    console.error('OAuth error:', error)
    alert(`Gmail connection failed: ${error}`)
    // Clear the error from the URL
    window.history.replaceState({}, '', window.location.pathname)
  }

  // Fetch accounts (will get the newly connected one if OAuth succeeded)
  await emails.fetchAccounts()
})

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

async function handleConnectGmail() {
  try {
    const { data } = await api.get<{ authorization_url: string }>(
      '/gmail/oauth/authorize'
    )
    // Redirect to Google's consent screen
    window.location.href = data.authorization_url
  } catch (error) {
    console.error('Failed to start OAuth flow:', error)
    alert('Failed to connect Gmail. Please try again.')
  }
}

async function handleSync() {
  await emails.syncNow()
  // New jobs land at the top, so jump back to page 1 to show them.
  await jobs.fetchJobs(1)
}

async function handleBackfill() {
  await emails.backfillJobs()
  await jobs.fetchJobs(1)
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 p-8">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-slate-900">Job Alert Extraction Dashboard</h1>
      <button
        class="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        @click="router.push('/scraper')"
      >
        Job Scraper
      </button>
    </div>

    <!-- Backend + Gmail connection status -->
    <div class="mt-6 grid gap-4 sm:grid-cols-2">
      <div class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p class="text-sm text-slate-500">Backend connection</p>
        <p v-if="overview.status === 'loading'" class="text-slate-700">Checking…</p>
        <p v-else-if="overview.status === 'ready'" class="font-medium text-emerald-600">
          Connected ({{ overview.backendStatus }})
        </p>
        <p v-else-if="overview.status === 'error'" class="font-medium text-red-600">
          Could not reach backend.
        </p>
      </div>

      <div class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p class="text-sm text-slate-500">Gmail account</p>
        <div v-if="connectedAccount" class="flex items-center justify-between">
          <p class="font-medium text-emerald-600">
            {{ connectedAccount.email }}
          </p>
        </div>
        <div v-else class="flex items-center justify-between">
          <p class="font-medium text-amber-600">No account connected</p>
          <button
            class="rounded-md bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700"
            @click="handleConnectGmail"
          >
            Connect Gmail
          </button>
        </div>
      </div>
    </div>

    <!-- Sync controls -->
    <div class="mt-6 flex items-center gap-4">
      <button
        class="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        :disabled="emails.syncing || !connectedAccount"
        @click="handleSync"
      >
        {{ emails.syncing ? 'Syncing…' : 'Sync Now' }}
      </button>
      <button
        class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        :disabled="emails.backfilling || !connectedAccount"
        @click="handleBackfill"
        title="Reprocess already-synced emails that don't have an extracted job yet"
      >
        {{ emails.backfilling ? 'Backfilling…' : 'Backfill Jobs' }}
      </button>
      <span v-if="emails.error" class="text-sm text-red-600">{{ emails.error }}</span>
      <span
        v-if="emails.lastSyncResults.length > 0 && !emails.syncing"
        class="text-sm text-slate-500"
      >
        Last sync: {{ emails.lastSyncResults[0].messages_found }} found,
        {{ emails.lastSyncResults[0].messages_ingested }} new,
        {{ emails.lastSyncResults[0].messages_skipped_duplicate }} duplicates skipped
      </span>
    </div>

    <!-- Jobs table -->
    <section class="mt-8">
      <h2 class="text-lg font-semibold text-slate-900">Jobs ({{ jobs.total }})</h2>
      <p class="mt-1 text-sm text-slate-500">
        Matched against your configured categories, deduplicated by fingerprint.
      </p>

      <div class="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table class="min-w-full divide-y divide-slate-200 text-sm">
          <thead class="bg-slate-50">
            <tr>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Title</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Company</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Source</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Categories</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Posted</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Received</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Link</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="jobs.jobs.length === 0">
              <td colspan="7" class="px-4 py-6 text-center text-slate-400">
                No jobs yet — connect Gmail and click "Sync Now".
              </td>
            </tr>
            <tr
              v-for="job in jobs.jobs"
              :key="job.id"
              :class="{ 'bg-slate-50/70': jobs.isVisited(job.job_url) }"
            >
              <td
                class="px-4 py-2"
                :class="jobs.isVisited(job.job_url) ? 'text-slate-400' : 'text-slate-800'"
              >
                {{ job.title }}
              </td>
              <td class="px-4 py-2 text-slate-600">{{ job.company ?? '—' }}</td>
              <td class="px-4 py-2 text-slate-600">{{ job.source ?? '—' }}</td>
              <td class="px-4 py-2 text-slate-600">{{ job.categories.join(', ') || '—' }}</td>
              <td class="px-4 py-2 text-slate-500">{{ formatDate(job.job_posted_at) }}</td>
              <td class="px-4 py-2 text-slate-500">{{ formatDate(job.received_at) }}</td>
              <td class="whitespace-nowrap px-4 py-2">
                <a
                  v-if="job.job_url"
                  :href="job.job_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="hover:underline"
                  :class="jobs.isVisited(job.job_url) ? 'text-slate-400' : 'text-blue-600'"
                  @click="jobs.markVisited(job.job_url)"
                  >Open</a
                >
                <span v-else class="text-slate-300">—</span>
                <span
                  v-if="jobs.isVisited(job.job_url)"
                  class="ml-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600"
                  title="You opened this link"
                  >✓ Visited</span
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- Pagination -->
      <div v-if="jobs.totalPages > 1" class="mt-3 flex items-center justify-between">
        <p class="text-sm text-slate-500">
          Page {{ jobs.page }} of {{ jobs.totalPages }} · {{ jobs.total }} jobs · newest first
        </p>
        <div class="flex items-center gap-2">
          <button
            class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="jobs.page <= 1 || jobs.loading"
            @click="jobs.goToPage(jobs.page - 1)"
          >
            ← Prev
          </button>
          <button
            class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="jobs.page >= jobs.totalPages || jobs.loading"
            @click="jobs.goToPage(jobs.page + 1)"
          >
            Next →
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
