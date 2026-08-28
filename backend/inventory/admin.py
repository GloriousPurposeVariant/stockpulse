from django import forms
from django.contrib import admin

from .models import Product, StockMovement
from .services import InsufficientStock, record_movement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price", "quantity", "updated_at")
    search_fields = ("sku", "name")
    readonly_fields = ("quantity", "created_at", "updated_at")


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ("product", "delta", "reason")

    def clean(self):
        # Advisory only, exactly like the order serializer's check. Stock can
        # be taken between here and the locked read inside record_movement,
        # so this exists to turn the common case into a field error rather
        # than a 500.
        cleaned = super().clean()
        product = cleaned.get("product")
        delta = cleaned.get("delta")
        if product and delta and product.quantity + delta < 0:
            raise forms.ValidationError(
                f"{product.sku} has {product.quantity} on hand; "
                f"this movement would take it to {product.quantity + delta}."
            )
        return cleaned


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    form = StockMovementForm
    list_display = ("product", "delta", "reason", "created_at")
    list_filter = ("reason",)
    search_fields = ("product__sku", "product__name")

    # Existing rows are history. Only the add form is writable, and even that
    # does not write directly - see save_model.
    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ("created_at",)
        return ("product", "delta", "reason", "created_at")

    # The ledger is append-only, and the only thing allowed to append to it is
    # the code that adjusts Product.quantity in the same transaction. Editing a
    # movement by hand would leave the cached quantity describing a history that
    # no longer exists.

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Not obj.save(). record_movement takes the row lock, updates the
        # cached quantity and publishes stock.changed in one transaction -
        # a bare save would write a ledger row that changes nothing.
        try:
            movement = record_movement(
                product_id=obj.product_id,
                delta=obj.delta,
                reason=obj.reason,
            )
        except InsufficientStock as exc:
            raise forms.ValidationError(str(exc)) from exc
        # The admin redirects using obj.pk after this returns, and the row
        # that was actually created is movement, not obj.
        obj.pk = movement.pk
