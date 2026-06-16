from rest_framework import serializers
from .models import Task, Worker, Manager, Status

class ManagerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Manager
        fields = '__all__'
    
class WorkerSerializer(serializers.ModelSerializer):

    manager = ManagerSerializer(read_only=True, source='manager_id')

    class Meta:
        model = Worker
        fields = '__all__'

class TaskSerializer(serializers.ModelSerializer):

    # Nested serializer to include worker details in the task representation
    assigned_to = WorkerSerializer(read_only=True)

    class Meta:
        model = Task
        fields = '__all__'
    
    
    def validate_status(self, value):
        if value.lower() not in [status.value.lower() for status in Status]:
            raise serializers.ValidationError("Invalid status. Allowed values are: Pending, In Progress, Completed.")
        return value