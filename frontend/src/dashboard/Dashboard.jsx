import { useEffect, useState } from "react"

import { api } from "../api/client.js"
import { useAuth } from "../auth/AuthContext.jsx"
import OrderList from "./OrderList.jsx"
import StockList from "./StockList.jsx"
import OrderForm from "./OrderForm.jsx"

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [status, setStatus] = useState("loading")

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        // Both at once rather than one after the other. They do not depend on
        // each other, so awaiting them in sequence would just be slower.
        const [orderPage, productPage] = await Promise.all([
          api("/api/v1/orders/"),
          api("/api/v1/products/"),
        ])
        if (cancelled) return
        // .results, not the response: DRF paginates, and the array is nested
        // inside { count, next, previous, results }.
        setOrders(orderPage.results)
        setProducts(productPage.results)
        setStatus("ready")
      } catch {
        if (!cancelled) setStatus("error")
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  // Functional update: the 201 response is the order, so there is nothing to
  // refetch. Newest first, matching the API's own ordering.
  const addOrder = (order) => setOrders((current) => [order, ...current])

  return (
    <div className="app">
      <header>
        <h1>StockPulse</h1>
        <div>
          <span>{user.username}</span>
          <button onClick={logout}>Sign out</button>
        </div>
      </header>

      {status === "loading" && <p className="empty">Loading…</p>}
      {status === "error" && (
        <p role="alert">Could not load your dashboard. Is the server running?</p>
      )}
      {status === "ready" && (
        <main>
          <OrderForm products={products} onCreated={addOrder} />
          <StockList products={products} />
          <OrderList orders={orders} />
        </main>

      )}
    </div>
  )
}
