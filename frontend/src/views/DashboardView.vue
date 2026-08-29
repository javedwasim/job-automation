<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useOverviewStore } from '../stores/overview'
import { useEmailsStore } from '../stores/emails'
import { useJobsStore } from '../stores/jobs'

const overview = useOverviewStore()
const emails = useEmailsStore()
const jobs = useJobsStore()

const connectedAccount = computed(() => emails.accounts[0] ?? null)

onMounted(() => {
  overview.checkBackend()
  emails.fetchAccounts()
  emails.fetchEmails()
  jobs.fetchJobs()
})

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

async function handleSync() {
  await emails.syncNow()
  await jobs.fetchJobs()
}

async function handleBackfill() {
  await emails.backfillJobs()
  await jobs.fetchJobs()
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 p-8">
    <h1 class="text-2xl font-semibold text-slate-900">Job Alert Extraction Dashboard</h1>

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
        <p v-if="connectedAccount" class="font-medium text-emerald-600">
          {{ connectedAccount.email }}
        </p>
        <p v-else class="font-medium text-amber-600">No account connected</p>
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
      <h2 class="text-lg font-semibold text-slate-900">Jobs ({{ jobs.jobs.length }})</h2>
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
            <tr v-for="job in jobs.jobs" :key="job.id">
              <td class="px-4 py-2 text-slate-800">{{ job.title }}</td>
              <td class="px-4 py-2 text-slate-600">{{ job.company ?? '—' }}</td>
              <td class="px-4 py-2 text-slate-600">{{ job.source ?? '—' }}</td>
              <td class="px-4 py-2 text-slate-600">{{ job.categories.join(', ') || '—' }}</td>
              <td class="px-4 py-2 text-slate-500">{{ formatDate(job.job_posted_at) }}</td>
              <td class="px-4 py-2 text-slate-500">{{ formatDate(job.received_at) }}</td>
              <td class="px-4 py-2">
                <a
                  v-if="job.job_url"
                  :href="job.job_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-blue-600 hover:underline"
                  >Open</a
                >
                <span v-else class="text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Discovered emails -->
    <section class="mt-8">
      <h2 class="text-lg font-semibold text-slate-900">
        Discovered emails ({{ emails.emails.length }})
      </h2>
      <p class="mt-1 text-sm text-slate-500">
        Every job-alert email found in the last 24 hours, whether or not it produced a job.
      </p>

      <div class="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table class="min-w-full divide-y divide-slate-200 text-sm">
          <thead class="bg-slate-50">
            <tr>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Subject</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Sender</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Source</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Received</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="emails.emails.length === 0">
              <td colspan="5" class="px-4 py-6 text-center text-slate-400">
                No emails discovered yet.
              </td>
            </tr>
            <tr v-for="email in emails.emails" :key="email.id">
              <td class="px-4 py-2 text-slate-800">{{ email.subject }}</td>
              <td class="px-4 py-2 text-slate-600">{{ email.sender }}</td>
              <td class="px-4 py-2 text-slate-600">{{ email.source ?? '—' }}</td>
              <td class="px-4 py-2 text-slate-500">{{ formatDate(email.received_at) }}</td>
              <td class="px-4 py-2 text-slate-500">{{ email.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
