from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Manager, Worker

User = get_user_model()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.Serializer):
    """
    Accepts user credentials + role-specific fields.
    Creates a CustomUser and the matching Manager or Worker profile in one transaction.
    """

    # User fields
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    # Profile fields
    dept = serializers.CharField(max_length=50)

    # Worker-only fields (required when role == 'worker')
    manager_id = serializers.IntegerField(required=False, help_text="Required for workers. PK of their manager.")
    role_title = serializers.CharField(max_length=50, required=False, help_text="Required for workers.")

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["role"] == User.ROLE_WORKER:
            if not attrs.get("manager_id"):
                raise serializers.ValidationError({"manager_id": "This field is required for workers."})
            if not attrs.get("role_title"):
                raise serializers.ValidationError({"role_title": "This field is required for workers."})
            if not Manager.objects.filter(pk=attrs["manager_id"]).exists():
                raise serializers.ValidationError({"manager_id": "Manager does not exist."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            role=validated_data["role"],
        )

        if validated_data["role"] == User.ROLE_MANAGER:
            Manager.objects.create(user=user, dept=validated_data["dept"])
        else:
            manager = Manager.objects.get(pk=validated_data["manager_id"])
            Worker.objects.create(
                user=user,
                dept=validated_data["dept"],
                manager=manager,
                role_title=validated_data["role_title"],
            )

        return user


# ---------------------------------------------------------------------------
# Custom JWT — embeds role in the token payload
# ---------------------------------------------------------------------------

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends SimpleJWT to include the user's role and profile id in the token
    so the frontend can make authorization decisions without extra API calls.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email

        if user.is_manager and hasattr(user, "manager_profile"):
            token["profile_id"] = user.manager_profile.pk
        elif user.is_worker and hasattr(user, "worker_profile"):
            token["profile_id"] = user.worker_profile.pk

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = self.user.role
        data["email"] = self.user.email
        data["user_id"] = self.user.pk
        return data


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

class UserProfileSerializer(serializers.ModelSerializer):
    """Returns the current user's info with nested manager/worker profile."""

    manager_profile = serializers.SerializerMethodField()
    worker_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "manager_profile",
            "worker_profile",
        ]
        read_only_fields = fields

    def get_manager_profile(self, obj):
        if obj.is_manager and hasattr(obj, "manager_profile"):
            profile = obj.manager_profile
            return {"manager_id": profile.pk, "dept": profile.dept}
        return None

    def get_worker_profile(self, obj):
        if obj.is_worker and hasattr(obj, "worker_profile"):
            profile = obj.worker_profile
            return {
                "worker_id": profile.pk,
                "dept": profile.dept,
                "manager_id": profile.manager_id,
                "role_title": profile.role_title,
            }
        return None
