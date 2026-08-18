import pytest

from orders.models import Order

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


def test_placing_an_order_not_move_stock(client_for, customer, widget):
    # Arrange: a client that places an order for 2 widgets.
    payload = {
        "items": [
            {"product": widget.pk, "quantity": 2},
        ],
    }

    # Act
    response = client_for(customer).post("/api/orders/", payload, format="json")

    # Assert: the order is created, but the product's stock is unchanged.
    assert response.status_code == 201
    widget.refresh_from_db()
    assert widget.quantity == 100


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
