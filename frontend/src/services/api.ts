import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api',
  withCredentials: true,
})

/**
 * Turns an unknown thrown value from an axios request into a readable message.
 *
 * FastAPI error responses carry a `detail` string (the `HTTPException`
 * shape), so surface that when present. When the request never reached the
 * backend at all (`error.response` is undefined — server down, wrong port,
 * CORS/network failure) point at connectivity instead of guessing at the
 * cause, and otherwise fall back to the HTTP status.
 */
export function extractApiError(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return fallback
  }
  const responseData = error.response?.data as { detail?: unknown } | undefined
  const detail = responseData?.detail
  if (typeof detail === 'string' && detail.trim() !== '') {
    return detail
  }
  if (error.response) {
    return `${fallback} (HTTP ${error.response.status})`
  }
  return `${fallback} Could not reach the backend at ${api.defaults.baseURL}.`
}
