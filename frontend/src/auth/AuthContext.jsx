import { createContext, useContext, useState, useEffect } from 'react';

import { api } from "../api/client.js";
import { clearAccessToken, endSession, refresh, setAccessToken } from "../api/tokens.js";

const AuthContext = createContext();

export const useAuth = () => {
    const value = useContext(AuthContext)
    if (!value) {
        // Without this you get "cannot read property user of null" from somewhere
        // three components away, rather than the actual mistake.
        throw new Error("useAuth must be called inside <AuthProvider>")
    }
    return value
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    // Three states, not two. "We do not know yet" is different from "signed
    // out": treating them the same flashes the login form at someone who is
    // already signed in, every single page load.
    const [status, setStatus] = useState("loading")

    const retry = () => setStatus("loading")

    useEffect(() => {
        // Only this state means "go and find out". Without the guard the
        // effect would re-run on every status change, including the ones it
        // causes itself.
        if (status !== "loading") return

        let cancelled = false

        const restore = async () => {
            try {
                // The access token is gone - this is a fresh page load. The refresh
                // cookie is what survived, and this is where it earns its keep.
                await refresh()
                const me = await api("/api/v1/auth/me/")
                if (!cancelled) {
                    setUser(me)
                    setStatus("authenticated")
                }
            } catch (err) {
                if (cancelled) return
                if (err.status === 0 || err.status >= 500) {
                    // We could not ask. Saying "signed out" would be a guess, and the
                    // wrong one most of the time.
                    setStatus("unreachable")
                } else {
                    setUser(null)
                    setStatus("anonymous")
                }
            }
        }
        restore()
        // Runs on unmount. Without it, a refresh that resolves after the user has
        // navigated away sets state on a component that no longer exists.
        return () => {
            cancelled = true
        }
    }, [status])

    const login = async (username, password) => {
        const { access } = await api("/api/v1/auth/login/", {
            method: "POST",
            body: JSON.stringify({ username, password }),
        })
        setAccessToken(access)
        setUser(await api("/api/v1/auth/me/"))
        setStatus("authenticated")
    }

    const logout = async () => {
        try {
            await endSession()
        } finally {
            clearAccessToken()
            setUser(null)
            setStatus("anonymous")
        }
    }

    return (
        <AuthContext.Provider value={{ user, status, login, logout, retry }}>
            {children}
        </AuthContext.Provider>
    )
}
