import { useCallback, useEffect, useRef, useState } from "react"

import { api } from "../api/client.js"
import { connectEvents } from "../api/socket.js"
import { useAuth } from "../auth/context.js"
import OrderForm from "./OrderForm.jsx"
import OrderList from "./OrderList.jsx"
import StockList from "./StockList.jsx"

// One internal shape. The REST list carries the full items array; events carry
// a count, because fifty nested line objects on every socket frame to every
// tab is not a trade worth making for a column that shows a number.
const fromApi = (order) => ({ ...order, item_count: order.items.length })

const fromEvent = (data) => ({
  id: data.id,
  reference: data.reference,
  status: data.status,
  total: data.total,
  created_at: data.created_at,
  item_count: data.item_count,
})

// Placing an order produces the same row twice: once as the POST response and
// once as the order.created event. on_commit fires before DRF renders the
// response, so the websocket frame can arrive first - and neither arrival can
// assume it is the first. Merging by id makes the order of the two irrelevant.
const upsert = (current, row) => {
  const index = current.findIndex((order) => order.id === row.id)
  if (index === -1) return [row, ...current]
  const merged = [...current]
  merged[index] = { ...merged[index], ...row }
  return merged
}

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [status, setStatus] = useState("loading")
  const [live, setLive] = useState("reconnecting")

  // load() now runs on mount and again on every reconnect, so two can overlap.
  // Each run claims a number; if a newer one has started by the time this one
  // answers, its data is already stale and is dropped. This replaces the
  // `cancelled` flag, which only covered unmounting.
  const loadSeq = useRef(0)

  const load = useCallback(async () => {
    const seq = ++loadSeq.current
    try {
      // Both at once rather than one after the other. They do not depend on
      // each other, so awaiting them in sequence would just be slower.
      const [orderPage, productPage] = await Promise.all([
        api("/api/v1/orders/"),
        api("/api/v1/products/"),
      ])
      if (seq !== loadSeq.current) return
      // .results, not the response: DRF paginates, and the array is nested
      // inside { count, next, previous, results }.
      setOrders(orderPage.results.map(fromApi))
      setProducts(productPage.results)
      setStatus("ready")
    } catch {
      if (seq !== loadSeq.current) return
      setStatus("error")
    }
  }, [])

  useEffect(() => {
    // The rule targets effects that set state to derive it from other state.
    // This one fetches from a server, which is what effects are for - and it
    // cannot be left to the socket's onStatus callback, because the dashboard
    // has to load even when the websocket service is unavailable.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  // Every branch uses the functional form. These run from a WebSocket message,
  // outside React's event system entirely, so the closure they were created in
  // may be several renders old.
  const applyEvent = useCallback((event) => {
    const { type, data } = event

    if (type === "order.created") {
      setOrders((current) => upsert(current, fromEvent(data)))
    } else if (type === "order.status_changed") {
      setOrders((current) =>
        current.map((order) =>
          order.id === data.id ? { ...order, status: data.status } : order,
        ),
      )
    } else if (type === "stock.changed") {
      setProducts((current) =>
        current.map((product) =>
          product.id === data.product_id
            ? { ...product, quantity: data.quantity }
            : product,
        ),
      )
    }
  }, [])

  useEffect(
    () =>
      connectEvents({
        onEvent: applyEvent,
        onStatus: (next) => {
          setLive(next)
          // Redis pub/sub has no replay, so anything published while we were
          // disconnected is gone for good. Re-reading the current state from
          // REST every time the connection comes back is the only cure.
          if (next === "live") load()
        },
      }),
    [applyEvent, load],
  )

  const addOrder = (order) => setOrders((current) => upsert(current, fromApi(order)))

  return (
    <div className="app">
      <header>
        <h1>StockPulse</h1>
        <div>
          <span className={`dot dot-${live}`} title={live} />
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
