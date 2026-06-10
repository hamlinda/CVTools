import axios from 'axios'

// Use Vite env var when provided, otherwise use relative paths so dev proxy works.
let base = (import.meta.env.VITE_BACKEND_URL as string) || ''

// If the configured base uses the docker-compose service name `backend`,
// browsers running on the host won't be able to resolve that name. When
// running in a browser, rewrite the hostname to the page's host so requests
// go to the same machine (useful for local dev where backend is reachable at
// the host IP or localhost). This only runs when `window` is available.
try {
  if (base && typeof window !== 'undefined') {
    const url = new URL(base)
    if (url.hostname === 'backend') {
      // Preserve scheme and port, but swap hostname to the page's host
      const port = url.port ? `:${url.port}` : ''
      base = `${window.location.protocol}//${window.location.hostname}${port}`
    }
  }
} catch (e) {
  // If URL parsing fails, leave base as-is (fallback to relative paths)
}

const api = axios.create({
  baseURL: base,
  withCredentials: false,
})

export default api
