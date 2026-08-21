import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
import redis

import event


@pytest.fixture
def fake_redis(monkeypatch):
    # spec restricts the mock to redis.Redis's real attributes, so a typo in the
    # code under test raises instead of silently recording a call that no real
    # client would accept.
    client = Mock(spec=redis.Redis)
    monkeypatch.setattr(event, "_redis", client)
    return client


def published(fake_redis):
    channel, payload = fake_redis.publish.call_args.args
    return channel, json.loads(payload)


def test_publish_wraps_data_in_an_envelope(fake_redis):
    # Act
    data = {"foo": "bar"}
    event.publish(event.ORDERS_CHANNEL, event.ORDER_CREATED, data)

    # Assert
    channel, payload = published(fake_redis)
    assert channel == event.ORDERS_CHANNEL
    assert payload["type"] == event.ORDER_CREATED
    assert payload["version"] == 1
    assert payload["data"] == data
    # The consumer dedupes on id after a reconnect and drops stale messages by
    # comparing occurred_at, so both must always be present.
    assert "id" in payload
    assert "occurred_at" in payload


def test_publish_serialises_decimals_and_datetimes(fake_redis):
    # Act
    data = {
        "price": Decimal("12.34"),
        "timestamp": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
    }
    event.publish(event.STOCKS_CHANNEL, event.STOCK_CHANGED, data)

    # Assert: Decimal becomes a string so no precision is lost, and
    # DjangoJSONEncoder writes a UTC offset as Z rather than +00:00.
    channel, payload = published(fake_redis)
    assert channel == event.STOCKS_CHANNEL
    assert payload["data"]["price"] == "12.34"
    assert payload["data"]["timestamp"] == "2024-01-01T12:00:00Z"


def test_publish_never_raises_when_redis_is_down(fake_redis, caplog):
    # Arrange
    caplog.set_level(logging.ERROR)
    fake_redis.publish.side_effect = redis.RedisError("Redis is down")

    # Act: an uncaught exception here would fail the test on its own.
    event.publish(event.ORDERS_CHANNEL, event.ORDER_CREATED, {"foo": "bar"})

    # Assert: the failure was swallowed, but not silently.
    assert "Failed to publish" in caplog.text
