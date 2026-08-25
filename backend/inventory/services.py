from functools import partial

from django.db import transaction

import event

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

    movement = StockMovement.objects.create(
        product=product,
        delta=delta,
        reason=reason,
        order=order,
    )

    # Built eagerly: the callback runs after the transaction has closed and
    # must not touch the database. No customer_id - stock is public, so the
    # websocket service broadcasts this to every connection.
    payload = {
        "product_id": product.pk,
        "sku": product.sku,
        "name": product.name,
        "quantity": product.quantity,
        "delta": delta,
        "reason": reason,
    }
    transaction.on_commit(
        partial(event.publish, event.STOCKS_CHANNEL, event.STOCK_CHANGED, payload)
    )
    return movement
