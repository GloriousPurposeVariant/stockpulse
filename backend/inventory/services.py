from django.db import transaction

from .models import Product, StockMovement


class InsufficientStock(Exception):
    pass


@transaction.atomic
def record_movement(*, product_id, delta, reason, order=None):
    product = Product.objects.select_for_update().get(pk=product_id)

    new_quantity = product.quantity + delta

    if new_quantity < 0:
        raise InsufficientStock(f"{product.sku}: have {product.quantity}, requested {-delta}")

    product.quantity = new_quantity
    product.save(update_fields=["quantity"])

    return StockMovement.objects.create(
        product=product,
        delta=delta,
        reason=reason,
        order=order,
    )
