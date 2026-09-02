import { AuthProvider, useAuth } from "./auth/AuthContext.jsx"
import LoginForm from "./auth/LoginForm.jsx"

function Dashboard() {
  const { user, logout } = useAuth()
  return (
    <>
      <h1>StockPulse</h1>
      <p>Signed in as {user.username}</p>
      <button onClick={logout}>Sign out</button>
    </>
  )
}

// Separate from App because a component cannot call useAuth and render the
// provider that supplies it - the context is only available to children.
function Shell() {
  const { status } = useAuth()
  if (status === "loading") return <p>Loading…</p>
  return status === "authenticated" ? <Dashboard /> : <LoginForm />
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}