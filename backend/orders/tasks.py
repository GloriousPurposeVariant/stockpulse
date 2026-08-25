import logging
from functools import partial

from celery import shared_task
from django.db import transaction

import event
from inventory.models import StockMovement
from inventory.services import InsufficientStock, record_movement

from .models import Order

logger = logging.getLogger(__name__)


def _publish_status(order, reason=None):
    payload = {
        "id": order.pk,
        "reference": order.reference,
        "status": order.status,
        "customer_id": order.customer_id,
    }
    if reason:
        payload["reason"] = reason
    transaction.on_commit(
        partial(event.publish, event.ORDERS_CHANNEL, event.ORDER_STATUS_CHANGED, payload)
    )


def _mark_failed(order_id, reason):
    # The transaction that raised has been rolled back, so the status change
    # has to be written in one of its own.
    logger.warning("order %s failed: %s", order_id, reason)
    with transaction.atomic():
        order = Order.objects.get(pk=order_id)
        order.status = Order.Status.FAILED
        order.save(update_fields=["status"])
        _publish_status(order, reason=reason)


@shared_task
def process_order(order_id):
    failure = None

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        if order.status != Order.Status.PENDING:
            return f"{order.reference}: already {order.status}, skipping"

        try:
            for item in order.items.select_related("product").order_by("product_id"):
                record_movement(
                    product_id=item.product_id,
                    delta=-item.quantity,
                    reason=StockMovement.Reason.ORDER,
                    order=order,
                )
        except InsufficientStock as exc:
            # Undo every deduction made so far - a partially filled order with
            # no record of it is worse than a clean failure.
            transaction.set_rollback(True)
            failure = str(exc)
        else:
            order.status = Order.Status.COMPLETED
            order.save(update_fields=["status"])
            _publish_status(order)

    if failure is None:
        return f"order {order_id}: completed"

    _mark_failed(order_id, failure)
    return f"order {order_id}: failed - {failure}"
