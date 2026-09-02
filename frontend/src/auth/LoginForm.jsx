import { useState } from "react"

import { useAuth } from "./AuthContext.jsx"

export default function LoginForm() {
    const { login } = useAuth()
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState(null)
    const [busy, setBusy] = useState(false)

    const submit = async (event) => {
        event.preventDefault()
        setBusy(true)
        setError(null)
        try {
            await login(username, password)
            // No setBusy(false) on success: this component unmounts the moment
            // status flips to authenticated, and setting state on it would warn.
        } catch (err) {
            setError(
                err.status === 0 || err.status >= 500
                    ? "Cannot reach the server."
                    : err.status === 401
                        ? "That username and password do not match."
                        : "Something went wrong. Please try again.",
            )

            setBusy(false)
        }
    }

    return (
        <form onSubmit={submit}>
            <h1>StockPulse</h1>

            <label htmlFor="username">Username</label>
            <input
                id="username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
            />

            <label htmlFor="password">Password</label>
            <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />

            {error && <p role="alert">{error}</p>}

            <button type="submit" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
            </button>
        </form>
    )
}