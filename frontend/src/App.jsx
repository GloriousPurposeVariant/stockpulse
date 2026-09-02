import { AuthProvider, useAuth } from "./auth/AuthContext.jsx"
import LoginForm from "./auth/LoginForm.jsx"
import Dashboard from "./dashboard/Dashboard.jsx"

// Separate from App because a component cannot call useAuth and render the
// provider that supplies it - the context is only available to children.
function Shell() {
  const { status, retry } = useAuth()
  if (status === "loading") return <p className="empty">Loading…</p>
  if (status === "unreachable") {
    return (
      <div className="app">
        <p role="alert">Cannot reach the server.</p>
        <button onClick={retry}>Try again</button>
      </div>
    )
  }
  return status === "authenticated" ? <Dashboard /> : <LoginForm />
}


export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}