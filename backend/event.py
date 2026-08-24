import json
import logging
import uuid

import redis
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

logger = logging.getLogger(__name__)

_redis = redis.Redis.from_url(settings.REDIS_URL)

ORDERS_CHANNEL = "stockpulse:orders"
STOCKS_CHANNEL = "stockpulse:stock"

ORDER_CREATED = "order.created"
ORDER_STATUS_CHANGED = "order.status_changed"
STOCK_CHANGED = "stock.changed"


def publish(channel, event_type, data, version=1):
    """Publish an event. Best-effort: never raises, never blocks an order."""
    envelope = {
        "type": event_type,
        "version": version,
        "id": str(uuid.uuid4()),
        "occurred_at": timezone.now(),
        "data": data,
    }
    try:
        _redis.publish(channel, json.dumps(envelope, cls=DjangoJSONEncoder))
    except redis.RedisError:
        logger.exception("Failed to publish %s to %s", event_type, channel)
