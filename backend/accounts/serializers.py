from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # Named explicitly, as everywhere else. __all__ on a user model is how
        # password hashes and is_superuser end up in a response.
        fields = ("id", "username", "email", "is_staff")
        read_only_fields = fields
