import { clearAccessToken, getAccessToken, refresh } from "./tokens.js"

const BASE_DELAY_MS = 500
const MAX_DELAY_MS = 30_000

// Exponential, with full jitter. Without the randomness every client that
// dropped when the server restarted comes back at the same instant and knocks
// it over again - a thundering herd of your own making.
const delayFor = (attempt) =>
  Math.random() * Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** attempt)

export const connectEvents = ({ onEvent, onStatus }) => {
  let socket = null
  let timer = null
  let attempt = 0
  let closed = false

  const schedule = () => {
    if (closed) return
    onStatus("reconnecting")
    timer = setTimeout(open, delayFor(attempt))
    attempt += 1
  }

  const open = async () => {
    if (closed) return

    // The token goes in the query string because a browser cannot set headers
    // on a WebSocket handshake. If we have none - first connect, or the server
    // rejected the last one - mint a fresh one before trying.
    let token = getAccessToken()
    if (!token) {
      try {
        token = await refresh()
      } catch {
        schedule()
        return
      }
    }
    // The component may have unmounted during that await.
    if (closed) return

    const scheme = location.protocol === "https:" ? "wss:" : "ws:"
    socket = new WebSocket(
      `${scheme}//${location.host}/ws?token=${encodeURIComponent(token)}`,
    )

    socket.onopen = () => {
      attempt = 0
      onStatus("live")
    }

    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data))
      } catch {
        // One malformed frame is not worth tearing the connection down over.
      }
    }

    socket.onclose = (event) => {
      socket = null
      if (closed) return
      // 4401 is the ws service rejecting the token. Discard it so the next
      // attempt refreshes rather than replaying something already refused.
      if (event.code === 4401) clearAccessToken()
      schedule()
    }

    // onclose always follows onerror, so reconnection is handled in one place.
    socket.onerror = () => {}
  }

  open()

  return () => {
    closed = true
    clearTimeout(timer)
    if (socket) {
      // Detach first: closing on purpose must not schedule a reconnect, and
      // StrictMode unmounts every component once in development.
      socket.onclose = null
      socket.close(1000, "client shutting down")
    }
  }
}
