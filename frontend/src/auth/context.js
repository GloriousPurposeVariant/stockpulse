import { createContext, useContext } from "react"

export const AuthContext = createContext(null)

export const useAuth = () => {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error("useAuth must be called inside <AuthProvider>")
  }
  return value
}
