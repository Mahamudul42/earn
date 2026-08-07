from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from rest_framework import serializers

from .roles import HUMAN_RATER_GROUP, is_human_rater

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    is_researcher = serializers.BooleanField(source="is_staff", read_only=True)
    role = serializers.SerializerMethodField()
    can_manage_raters = serializers.SerializerMethodField()
    rating_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_researcher",
            "role",
            "can_manage_raters",
            "is_active",
            "rating_count",
            "last_login",
            "date_joined",
        ]

    def get_role(self, obj):
        return "rater" if is_human_rater(obj) else "manager"

    def get_can_manage_raters(self, obj):
        return bool(obj.is_staff and not is_human_rater(obj))


class RaterCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(
            **validated_data,
            password=password,
            is_staff=True,
        )
        group, _ = Group.objects.get_or_create(name=HUMAN_RATER_GROUP)
        user.groups.add(group)
        return user


class RaterUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=False, min_length=12
    )

    class Meta:
        model = User
        fields = ["email", "is_active", "password"]

    def validate_password(self, value):
        validate_password(value, user=self.instance)
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance
