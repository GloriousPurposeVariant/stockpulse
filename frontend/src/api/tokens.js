import { ApiError } from "./errors.js"

// The access token lives here and nowhere else. Not localStorage, not
// sessionStorage: anything a script can read, an injected script can steal.
// It dies with the tab, and the httpOnly refresh cookie is what survives -
// which is why a new tab is logged in without the user doing anything.
let accessToken = null

export const getAccessToken = () => accessToken

export const setAccessToken = (token) => {
  accessToken = token
}

export const clearAccessToken = () => {
  accessToken = null
}

const readCookie = (name) => {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`))
  return match ? decodeURIComponent(match[2]) : null
}

// Django sets csrftoken deliberately *without* httpOnly, because the client
// has to echo it back in a header. That echo is the proof: another site can
// make the browser send the cookie, but the same-origin policy stops it from
// reading the value, so it cannot produce the header.
const csrfHeaders = () => {
  const token = readCookie("csrftoken")
  return token ? { "X-CSRFToken": token } : {}
}

export const ensureCsrfCookie = async () => {
  if (readCookie("csrftoken")) return
  await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" })
}

let inFlight = null

const requestRefresh = async () => {
  let response
  try {
    await ensureCsrfCookie()
    response = await fetch("/api/v1/auth/refresh/", {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders(),
    })
  } catch {
    // Unreachable, not unauthorised. Deliberately does NOT clear the access
    // token: the session may be perfectly valid and the server merely down.
    throw new ApiError(0, null)
  }

  if (!response.ok) {
    // Only an auth rejection ends the session. A 500, or a 502 from nginx
    // standing in for a dead gunicorn, means the server is unwell - not that
    // this user is signed out. Keep the token; it may still be perfectly good.
    if (response.status === 401 || response.status === 403) {
      clearAccessToken()
    }
    throw new ApiError(response.status, null)
  }


  const { access } = await response.json()
  setAccessToken(access)
  return access
}

// Older Safari has no Web Locks. Degrading to no cross-tab coordination is
// worse than having it, and far better than crashing.
const withLock = (name, fn) =>
  navigator.locks ? navigator.locks.request(name, fn) : fn()

export const refresh = () => {
  // Two guards, for two different races.
  //
  // inFlight: several API calls in *this* tab can get a 401 at the same
  // moment. Without it they fire several refreshes, and because rotation
  // blacklists the old token, all but the first present something already
  // dead - and the user is signed out mid-session.
  if (inFlight) return inFlight

  // The lock: the same race across *tabs*, which share one cookie. The lock
  // is held per origin, so a second tab waits; by the time it runs the cookie
  // holds the rotated token, and it refreshes from that instead of replaying
  // a blacklisted one.
  inFlight = withLock("auth-refresh", requestRefresh).finally(() => {
    inFlight = null
  })

  return inFlight
}

export const endSession = async () => {
  await ensureCsrfCookie()
  try {
    await fetch("/api/v1/auth/logout/", {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders(),
    })
  } finally {
    // Even if the request failed, this browser is done with the token. The
    // server-side blacklist is the part that can fail; forgetting locally
    // cannot, and must not be conditional on the network.
    clearAccessToken()
  }
}

