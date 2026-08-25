import pytest

from inventory.models import StockMovement

from .models import Order, OrderItem
from .tasks import process_order

pytestmark = pytest.mark.django_db


def make_order(customer, *lines):
    """lines: (product, quantity) pairs."""
    order = Order.objects.create(customer=customer)
    OrderItem.objects.bulk_create(
        OrderItem(order=order, product=product, quantity=quantity, unit_price=product.price)
        for product, quantity in lines
    )
    return order


def test_processing_an_order_deducts_stock_and_completes_it(customer, widget):
    # Arrange
    before = widget.quantity
    order = make_order(customer, (widget, 3))

    # Act
    process_order(order.pk)

    # Assert
    order.refresh_from_db()
    widget.refresh_from_db()
    assert widget.quantity == before - 3
    assert order.status == Order.Status.COMPLETED
    assert StockMovement.objects.count() == 1


def test_processing_an_order_twice_changes_nothing(customer, widget):
    # Arrange
    before = widget.quantity
    order = make_order(customer, (widget, 3))

    # Act: process twice
    process_order(order.pk)
    process_order(order.pk)

    # Assert
    order.refresh_from_db()
    widget.refresh_from_db()
    assert widget.quantity == before - 3
    assert order.status == Order.Status.COMPLETED
    assert StockMovement.objects.count() == 1


def test_an_order_beyond_stock_fails_and_moves_no_stock(customer, widget, gadget):
    # Arrange
    before_widget = widget.quantity
    before_gadget = gadget.quantity
    order = make_order(customer, (widget, 1), (gadget, 999))

    # Act
    process_order(order.pk)

    # Assert
    order.refresh_from_db()
    widget.refresh_from_db()
    gadget.refresh_from_db()
    assert widget.quantity == before_widget
    assert gadget.quantity == before_gadget
    assert order.status == Order.Status.FAILED
    assert StockMovement.objects.count() == 0
