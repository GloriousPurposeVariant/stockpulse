from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from inventory.models import Product


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
