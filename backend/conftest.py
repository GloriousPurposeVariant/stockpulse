from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import event
from inventory.models import Product
from orders.tasks import process_order


@pytest.fixture
def published_events(monkeypatch):
    """Replace event.publish with a Mock and hand it back for inspection.

    Patched at the publish() level rather than the Redis client: this file
    asserts *that* an event is emitted, while test_event.py owns the envelope.
    """
    mock = Mock()
    monkeypatch.setattr(event, "publish", mock)
    return mock


@pytest.fixture(autouse=True)
def enqueued_orders(monkeypatch):
    """Replace process_order.delay so tests never touch the real broker.

    Deliberately not CELERY_TASK_ALWAYS_EAGER: that runs the task inline
    inside the request, which is the exact opposite of what the API
    promises, and would make every existing order test move stock.
    """
    dispatch = Mock()
    monkeypatch.setattr(process_order, "delay", dispatch)
    return dispatch


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(username="alice", password="pw")


@pytest.fixture
def other_customer(db):
    return get_user_model().objects.create_user(username="bob", password="pw")


@pytest.fixture
def widget(db):
    # Decimal, not '19.99' — Django does not coerce field values on assignment,
    # so a string here would stay a string on the in-memory instance.
    return Product.objects.create(
        sku="WIDGET-01",
        name="Widget",
        price=Decimal("19.99"),
        quantity=100,
    )


@pytest.fixture
def gadget(db):
    return Product.objects.create(
        sku="GADGET-01",
        name="Gadget",
        price=Decimal("5.00"),
        quantity=10,
    )


@pytest.fixture
def client_for():
    """Return a factory that builds an APIClient authenticated as a given user."""

    def _client_for(user):
        client = APIClient()
        token = RefreshToken.for_user(user).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _client_for
