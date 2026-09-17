<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useScraperStore } from '../stores/scraper'

const scraper = useScraperStore()
const router = useRouter()

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

const datePostedOptions = [
  { value: 'any', label: 'Any time' },
  { value: 'past_24_hours', label: 'Past 24 hours' },
  { value: 'past_week', label: 'Past week' },
  { value: 'past_month', label: 'Past month' },
]

const jobTypeOptions = [
  { value: 'any', label: 'Any' },
  { value: 'full_time', label: 'Full-time' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'temporary', label: 'Temporary' },
  { value: 'internship', label: 'Internship' },
]

const workplaceOptions = [
  { value: 'any', label: 'Any' },
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
]
</script>

<template>
  <div class="min-h-screen bg-slate-50 p-8">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-slate-900">Job Scraper</h1>
      <button
        class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        @click="router.push('/')"
      >
        ← Back to Dashboard
      </button>
    </div>

    <!-- Search filters -->
    <section class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 class="mb-4 text-lg font-medium text-slate-800">Search filters</h2>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-600">Keyword</label>
          <input
            v-model="scraper.filters.keyword"
            type="text"
            placeholder="e.g. PHP Developer"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-600">Location</label>
          <input
            v-model="scraper.filters.location"
            type="text"
            placeholder="e.g. Remote, Pakistan, Lahore"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-600">Date Posted</label>
          <select
            v-model="scraper.filters.date_posted"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option v-for="opt in datePostedOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-600">Job Type</label>
          <select
            v-model="scraper.filters.job_type"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option v-for="opt in jobTypeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-600">Workplace</label>
          <select
            v-model="scraper.filters.workplace"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option v-for="opt in workplaceOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>
      <div class="mt-5 flex items-center gap-3">
        <button
          class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="scraper.running"
          @click="scraper.runScrape()"
        >
          <span v-if="scraper.running">Scraping…</span>
          <span v-else>Scrape LinkedIn Jobs</span>
        </button>
        <button
          class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          :disabled="scraper.running"
          @click="scraper.resetFilters()"
        >
          Reset
        </button>
      </div>
    </section>

    <!-- Loading / progress -->
    <div v-if="scraper.running" class="mt-6 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-700">
      Scraping LinkedIn — opening the search page, reading job cards, and saving results. This can take a minute…
    </div>

        <!-- Error -->
    <div v-if="scraper.error && !scraper.running" class="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
      {{ scraper.error }}
    </div>

    <section v-if="scraper.result" class="mt-6">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-lg font-medium text-slate-800">
          Scraped Jobs
          <span class="ml-2 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
            {{ scraper.result.source }}
          </span>
        </h2>
        <p class="text-sm text-slate-500">
          {{ scraper.result.saved }} new · {{ scraper.result.duplicates }} duplicate ·
          {{ scraper.result.filtered_by_date }} filtered by date · {{ scraper.result.total_found }} cards seen
        </p>
      </div>

      <div class="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table class="w-full text-left text-sm">
          <thead class="border-b border-slate-200 bg-slate-50">
            <tr>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Title</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Company</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Posted</th>
              <th class="px-4 py-2 text-left font-medium text-slate-600">Job Link</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="scraper.result.jobs.length === 0">
              <td colspan="4" class="px-4 py-6 text-center text-slate-400">
                No jobs matched these filters.
              </td>
            </tr>
            <tr v-for="job in scraper.result.jobs" :key="job.id">
              <td class="px-4 py-2 text-slate-800">{{ job.title }}</td>
              <td class="px-4 py-2 text-slate-600">{{ job.company ?? '—' }}</td>
              <td class="px-4 py-2 text-slate-500">{{ job.posted_text ?? formatDate(job.posted_at) }}</td>
              <td class="whitespace-nowrap px-4 py-2">
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
    </div>
</template>

