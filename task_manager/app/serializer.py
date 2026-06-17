from rest_framework import serializers
from .models import Task, Worker, Manager, Status


class ManagerSerializer(serializers.ModelSerializer):
    """Serializes Manager profile with user info pulled from the linked CustomUser."""

    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Manager
        fields = ['manager_id', 'first_name', 'last_name', 'email', 'dept']
        read_only_fields = ['manager_id']


class WorkerSerializer(serializers.ModelSerializer):
    """Serializes Worker profile with user info and nested manager details."""

    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    manager = ManagerSerializer(read_only=True)

    class Meta:
        model = Worker
        fields = [
            'worker_id', 'first_name', 'last_name', 'email',
            'dept', 'manager', 'role_title',
        ]
        read_only_fields = ['worker_id']


class TaskSerializer(serializers.ModelSerializer):
    """Serializes Task with nested worker details (read-only)."""

    # Read-only: nested worker info in responses
    assigned_to = WorkerSerializer(read_only=True)

    # Write-only: accepts a worker PK when creating/updating tasks
    assigned_to_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Task
        fields = '__all__'
        extra_kwargs = {
            'assigned_to': {'read_only': True},
        }

    def validate_status(self, value):
        if value.lower() not in [status.value.lower() for status in Status]:
            raise serializers.ValidationError("Invalid status. Allowed values are: Pending, In Progress, Completed.")
        return value