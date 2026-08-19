from unittest.mock import patch

import pytest

from inventory.models import StockMovement
from orders.models import Order
from orders.views import OrderViewSet

pytestmark = pytest.mark.django_db


def test_client_supplied_unit_price_is_ignored(client_for, customer, widget):
    # Arrange: a client that asks for a 19.99 widget at one penny.
    payload = {
        "items": [
            {"product": widget.pk, "quantity": 2, "unit_price": "0.01"},
        ],
    }

    # Act
    response = client_for(customer).post("/api/orders/", payload, format="json")

    # Assert: the order is created, priced from the product rather than the request.
    assert response.status_code == 201

    line = Order.objects.get(reference=response.data["reference"]).items.get()
    assert line.unit_price == widget.price
    assert response.data["total"] == "39.98"


def test_customer_sees_only_their_own_orders(client_for, customer, other_customer, widget):
    # Arrange: two customers each place an order for the same product.
    for user in (customer, other_customer):
        client_for(user).post(
            "/api/orders/",
            {
                "items": [{"product": widget.pk, "quantity": 1}],
            },
            format="json",
        )

    # Act
    response = client_for(customer).get("/api/orders/")

    # Assert: the first customer sees only their own order.
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["customer"] == customer.username

    response = client_for(other_customer).get("/api/orders/")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["customer"] == other_customer.username


def test_placing_an_order_does_not_move_stock(client_for, customer, widget):
    # Arrange: a client that places an order for 2 widgets.
    payload = {
        "items": [
            {"product": widget.pk, "quantity": 2},
        ],
    }
    before = widget.quantity

    # Act
    response = client_for(customer).post("/api/orders/", payload, format="json")

    # Assert: the order is created, but the product's stock is unchanged.
    assert response.status_code == 201
    widget.refresh_from_db()
    assert widget.quantity == before
    assert StockMovement.objects.count() == 0


def test_another_user_order_returns_404(client_for, customer, other_customer, widget):
    # Arrange: one user places an order.
    payload = {
        "items": [
            {"product": widget.pk, "quantity": 2},
        ],
    }
    response = client_for(customer).post("/api/orders/", payload, format="json")

    # Act: another user tries to retrieve that order.
    order_id = response.data["id"]
    response = client_for(other_customer).get(f"/api/orders/{order_id}/")

    assert response.status_code == 404


def test_replayed_request_returns_the_original_order(client_for, customer, widget):
    # Arrange
    client = client_for(customer)
    payload = {"items": [{"product": widget.pk, "quantity": 2}]}
    headers = {"Idempotency-Key": "test-idempotency-key"}

    # Act: the same request, sent twice
    first = client.post("/api/orders/", payload, format="json", headers=headers)
    second = client.post("/api/orders/", payload, format="json", headers=headers)

    # Assert: the second call replayed the first instead of creating another order
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.data["reference"] == second.data["reference"]
    assert Order.objects.count() == 1


def test_different_idempotency_keys_create_separate_orders(client_for, customer, widget):
    # Arrange
    client = client_for(customer)
    payload = {"items": [{"product": widget.pk, "quantity": 2}]}

    # Act: the different requests, sent with different idempotency keys
    first = client.post(
        "/api/orders/",
        payload,
        format="json",
        headers={"Idempotency-Key": "test-idempotency-key-1"},
    )
    second = client.post(
        "/api/orders/",
        payload,
        format="json",
        headers={"Idempotency-Key": "test-idempotency-key-2"},
    )
    # Assert: both calls created separate orders
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["reference"] != second.data["reference"]
    assert Order.objects.count() == 2


def test_same_key_from_different_customers_creates_separate_orders(
    client_for, customer, widget, other_customer
):
    # Arrange
    payload = {"items": [{"product": widget.pk, "quantity": 2}]}
    first_client = client_for(customer)
    second_client = client_for(other_customer)

    # Act: the different requests, sent with same idempotency keys
    first = first_client.post(
        "/api/orders/",
        payload,
        format="json",
        headers={"Idempotency-Key": "test-idempotency-key"},
    )
    second = second_client.post(
        "/api/orders/",
        payload,
        format="json",
        headers={"Idempotency-Key": "test-idempotency-key"},
    )
    # Assert: both calls created separate orders
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["customer"] == customer.username
    assert second.data["customer"] == other_customer.username
    assert first.data["reference"] != second.data["reference"]
    assert Order.objects.count() == 2


def test_replay_recovers_when_the_lookup_misses(client_for, customer, widget):
    # Arrange: an order already placed under this key.
    client = client_for(customer)
    payload = {"items": [{"product": widget.pk, "quantity": 2}]}
    headers = {"Idempotency-Key": "test-idempotency-key"}
    first = client.post("/api/orders/", payload, format="json", headers=headers)
    original = Order.objects.get(reference=first.data["reference"])

    # Act: replay it with the pre-flight lookup forced to miss, which is the
    # state two simultaneous requests are both in before either has committed.
    # _existing_order is called twice per request - once before inserting and
    # once while recovering - so the first answer is the forced miss and the
    # second is the real one. The insert, the unique constraint and the
    # IntegrityError it raises are all genuine.
    with patch.object(OrderViewSet, "_existing_order", side_effect=[None, original]):
        second = client.post("/api/orders/", payload, format="json", headers=headers)

    # Assert: the constraint rejected the duplicate and the recovery returned
    # the order that already existed.
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.data["reference"] == first.data["reference"]
    assert Order.objects.count() == 1
