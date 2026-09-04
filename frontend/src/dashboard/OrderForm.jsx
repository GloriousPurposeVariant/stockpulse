import { useRef, useState } from "react"

import { api } from "../api/client.js"

// DRF nests errors by field, and items is a list of objects, so one serializer
// error can arrive as {"items": ["..."]}, as {"items": [{"quantity": ["..."]}]},
// or as {"detail": "..."}. Walk down to the first string rather than rendering
// [object Object] at the user.
const firstMessage = (data) => {
  if (!data) return null
  if (typeof data === "string") return data
  if (Array.isArray(data)) return firstMessage(data[0])
  if (data.detail) return firstMessage(data.detail)
  return firstMessage(Object.values(data)[0])
}

export default function OrderForm({ products, onCreated }) {
  const [lines, setLines] = useState([])
  const [productId, setProductId] = useState("")
  const [quantity, setQuantity] = useState(1)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  // Names the order being attempted, not the button press. A retry after a
  // failure reuses it so the server recognises the replay; editing the lines
  // or placing the order makes it a different order and earns a new key.
  const key = useRef(crypto.randomUUID())
  const newKey = () => {
    key.current = crypto.randomUUID()
  }

  const addLine = () => {
    if (!productId) return
    setLines((current) => [
      ...current,
      { id: crypto.randomUUID(), productId: Number(productId), quantity },
    ])
    setProductId("")
    setQuantity(1)
    setError(null)
    newKey()
  }

  const removeLine = (id) => {
    setLines((current) => current.filter((line) => line.id !== id))
    setError(null)
    newKey()
  }

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const order = await api("/api/v1/orders/", {
        method: "POST",
        headers: { "Idempotency-Key": key.current },
        body: JSON.stringify({
          items: lines.map((line) => ({
            product: line.productId,
            quantity: line.quantity,
          })),
        }),
      })
      onCreated(order)
      setLines([])
      newKey()
    } catch (err) {
      setError(
        err.status === 400
          ? // A 400 whose body did not parse leaves nothing to show, and a
            // button that silently re-enables reads as the app ignoring you.
            (firstMessage(err.data) ?? "Could not place the order.")
          : err.status === 0 || err.status >= 500
            ? "Could not reach the server. Try again — the same order will not be placed twice."
            : "Could not place the order.",
      )
    } finally {
      setBusy(false)
    }
  }

  const productFor = (id) => products.find((product) => product.id === id)

  return (
    <section className="span-2">
      <h2>New order</h2>

      {/* Enter in the quantity box adds a line. Placing the order is a
          separate, deliberate action - not something a stray Enter does. */}
      <form
        className="order-form"
        onSubmit={(event) => {
          event.preventDefault()
          addLine()
        }}
      >
        <select value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">Choose a product…</option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.sku} — {product.name} ({product.quantity} on hand)
            </option>
          ))}
        </select>
        <input
          type="number"
          min="1"
          required
          value={quantity}
          onChange={(e) => setQuantity(Number(e.target.value))}
          aria-label="Quantity"
        />
        <button type="submit" disabled={!productId}>
          Add
        </button>
      </form>

      {lines.length > 0 && (
        <ul className="lines">
          {lines.map((line) => {
            const product = productFor(line.productId)
            return (
              <li key={line.id}>
                <span>
                  {line.quantity} × {product ? product.sku : line.productId}
                </span>
                <button type="button" onClick={() => removeLine(line.id)}>
                  Remove
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {error && <p role="alert">{error}</p>}

      <button type="button" onClick={submit} disabled={busy || lines.length === 0}>
        {busy ? "Placing…" : "Place order"}
      </button>
    </section>
  )
}
