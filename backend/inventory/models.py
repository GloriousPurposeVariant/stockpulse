from django.db import models


class Product(models.Model):
    """A sellable item.

    ``quantity`` is a cached figure derived from this product's StockMovement
    rows. The ledger is the source of truth; this field exists so that reading
    on-hand stock is a column read rather than an aggregate over the whole
    movement table.
    """

    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sku',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='product_price_non_negative',
            ),
        )

    def __str__(self):
        return f'{self.sku} — {self.name}'


class StockMovement(models.Model):
    """An immutable record of a single change to a product's stock.

    Rows are only ever appended. Correcting a mistake means writing an
    opposing movement, never editing or deleting an existing one, so the
    history always explains how the current quantity was reached.
    """

    class Reason(models.TextChoices):
        ORDER = 'order', 'Order'
        RESTOCK = 'restock', 'Restock'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        CANCELLATION = 'cancellation', 'Cancellation'
    
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='movements',
    )
    delta = models.IntegerField(
        help_text='Signed change in units: negative for a sale, positive for a restock.',
    )
    reason = models.CharField(max_length=32, choices=Reason.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = (
            models.Index(fields=('product', '-created_at')),
        )
        constraints = (
            models.CheckConstraint(
                condition=~models.Q(delta=0),
                name='stockmovement_delta_non_zero',
            ),
        )

    def __str__(self):
        return f'{self.product.sku} {self.delta:+d} ({self.reason})'
