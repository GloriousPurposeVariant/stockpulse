export default function StockList({ products }) {
  return (
    <section>
      <h2>Stock</h2>
      {products.length === 0 ? (
        <p className="empty">No products.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Name</th>
              <th className="num">Price</th>
              <th className="num">On hand</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product) => (
              <tr key={product.id}>
                <td>{product.sku}</td>
                <td>{product.name}</td>
                <td className="num">{product.price}</td>
                <td className="num">{product.quantity}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
