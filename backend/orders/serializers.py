from functools import partial

from django.db import transaction
from rest_framework import serializers

import event

from .models import Order, OrderItem
from .tasks import process_order


class OrderItemSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_sku",
            "product_name",
            "quantity",
            "unit_price",
            "subtotal",
        )
        # unit_price is copied from the product at creation. Accepting it from
        # the client would let anyone name their own price.
        read_only_fields = ("unit_price",)
        extra_kwargs = {
            "quantity": {"min_value": 1},
        }


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    customer = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "reference",
            "customer",
            "status",
            "items",
            "total",
            "created_at",
        )
        # Everything the pipeline owns. A client states what it wants; the
        # server decides the identity, the owner and the state.
        read_only_fields = ("reference", "status", "created_at")

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("An order must contain at least one item.")

        products = [item["product"] for item in items]
        if len(products) != len(set(products)):
            raise serializers.ValidationError(
                "Each product may appear only once. Combine the quantities instead."
            )

        # Advisory only. Stock can be taken by another order between this check
        # and the worker actually reserving it, so the authoritative check is
        # the locked read in the processing task. This exists to turn the
        # common case into a clear 400 instead of a failed order.
        for item in items:
            product = item["product"]
            if item["quantity"] > product.quantity:
                raise serializers.ValidationError(
                    f"Only {product.quantity} unit(s) of {product.sku} are available."
                )

        return items

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["product"].price,
            )
            for item in items_data
        )
        # Built eagerly: the callback runs after the transaction has closed, so
        # it must not touch the database. customer_id is what lets the websocket
        # service route this to one customer instead of broadcasting it.
        payload = {
            # The client keys rows by id, the same as the REST list does.
            # Without it a created order cannot be rendered, let alone matched
            # against the status change that follows it.
            "id": order.pk,
            "reference": order.reference,
            "status": order.status,
            "customer_id": order.customer_id,
            "total": order.total,
            "item_count": len(items_data),
            "created_at": order.created_at,
        }
        # on_commit, not a direct call: this method is atomic, and an event sent
        # before the commit would announce an order a rollback then erases.
        transaction.on_commit(
            partial(event.publish, event.ORDERS_CHANNEL, event.ORDER_CREATED, payload)
        )
        # Also on_commit: delay() hands the id to Redis immediately, and a
        # worker is a separate process with its own database connection. It can
        # pop the message while this transaction is still open, and its
        # connection cannot see rows this one has not committed yet - the task
        # would raise Order.DoesNotExist against an order that is right there.
        transaction.on_commit(partial(process_order.delay, order.pk))

        return order
