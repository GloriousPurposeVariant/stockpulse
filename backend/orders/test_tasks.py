import pytest

import event
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


def events_of_type(published_events, event_type):
    """The payloads of every publish call of one type, in order."""
    return [call.args[2] for call in published_events.call_args_list if call.args[1] == event_type]


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


def test_completing_an_order_publishes_a_status_change(
    customer, widget, published_events, django_capture_on_commit_callbacks
):
    # Arrange
    order = make_order(customer, (widget, 3))

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        process_order(order.pk)

    # Assert
    statuses = events_of_type(published_events, event.ORDER_STATUS_CHANGED)
    assert len(statuses) == 1
    assert statuses[0]["status"] == Order.Status.COMPLETED
    assert statuses[0]["reference"] == order.reference
    # Without this the websocket service has nobody to deliver it to.
    assert statuses[0]["customer_id"] == customer.id
    # And the stock movement was announced too - the contrast that makes the
    # zero in the failure test mean something.
    assert len(events_of_type(published_events, event.STOCK_CHANGED)) == 1


def test_a_failed_order_publishes_a_status_change(
    customer, widget, gadget, published_events, django_capture_on_commit_callbacks
):
    # Arrange: gadget has 10.
    order = make_order(customer, (widget, 1), (gadget, 999))

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        process_order(order.pk)

    # Assert
    statuses = events_of_type(published_events, event.ORDER_STATUS_CHANGED)
    assert len(statuses) == 1
    assert statuses[0]["status"] == Order.Status.FAILED
    assert statuses[0]["customer_id"] == customer.id
    assert "GADGET-01" in statuses[0]["reason"]


def test_a_failed_order_publishes_no_stock_events(
    customer, widget, gadget, published_events, django_capture_on_commit_callbacks
):
    # Arrange: the widget line can be filled, the gadget line cannot.
    order = make_order(customer, (widget, 1), (gadget, 999))

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        process_order(order.pk)

    # Assert: the widget was deducted and then rolled back, so announcing it
    # would tell every client about a movement that does not exist.
    assert events_of_type(published_events, event.STOCK_CHANGED) == []
