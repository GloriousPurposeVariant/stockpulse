import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.db import connection

from .models import Product, StockMovement
from .services import InsufficientStock, record_movement

pytestmark = pytest.mark.django_db


def test_record_movement_updates_quantity_and_writes_a_movement(widget):
    # Arrange
    before = widget.quantity

    # Act
    movement = record_movement(product_id=widget.pk, delta=50, reason=StockMovement.Reason.RESTOCK)

    # Assert
    widget.refresh_from_db()
    assert widget.quantity == before + 50
    assert StockMovement.objects.count() == 1
    assert movement.delta == 50
    assert movement.reason == StockMovement.Reason.RESTOCK


def test_a_movement_below_zero_is_rejected(widget):
    # Arrange
    before = widget.quantity

    # Act
    with pytest.raises(InsufficientStock):
        record_movement(
            product_id=widget.pk, delta=-(before + 1), reason=StockMovement.Reason.RESTOCK
        )

    # Assert
    widget.refresh_from_db()
    assert widget.quantity == before
    assert StockMovement.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_movements_cannot_oversell():
    product = Product.objects.create(
        sku="LAST-ONE", name="Last One", price=Decimal("9.99"), quantity=1
    )
    barrier = threading.Barrier(2)

    def take_one():
        barrier.wait()
        try:
            record_movement(
                product_id=product.pk,
                delta=-1,
                reason=StockMovement.Reason.ORDER,
            )
            return "ok"
        except InsufficientStock:
            return "rejected"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(take_one), pool.submit(take_one)]
        results = sorted(f.result() for f in futures)

    assert results == ["ok", "rejected"]

    product.refresh_from_db()
    assert product.quantity == 0
    assert StockMovement.objects.count() == 1
