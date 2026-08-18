from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models


def generate_reference():
    return f'ORD-{uuid4().hex[:10].upper()}'


class Order(models.Model):
    """A customer's request for stock.

    An order records intent only. Nothing here touches Product.quantity —
    that happens when the order is processed, via a StockMovement.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    reference = models.CharField(max_length=32, unique=True, default=generate_reference)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text='Client-supplied key. A retry carrying a key already seen '
                  'returns the original order instead of creating a second one.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = (
            models.Index(fields=('status', '-created_at')),
        )
        constraints = (
            models.UniqueConstraint(
                fields=('customer', 'idempotency_key'),
                name='order_unique_customer_idempotency_key',
            ),
        )

    def __str__(self):
        return f'{self.reference} ({self.status})'

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), Decimal('0.00'))


class OrderItem(models.Model):
    """A single product line on an order.

    ``unit_price`` is copied from the product when the line is created rather
    than looked up later, so repricing a product never rewrites the value of
    orders already placed.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=('order', 'product'),
                name='orderitem_unique_product_per_order',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='orderitem_quantity_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name='orderitem_unit_price_non_negative',
            ),
        )

    def __str__(self):
        return f'{self.quantity} × {self.product.sku}'

    @property
    def subtotal(self):
        return self.quantity * self.unit_price
