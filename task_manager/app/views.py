from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from .models import Task, Worker, Manager
from .serializer import TaskSerializer, WorkerSerializer, ManagerSerializer

# Create your views here.

def get_user_manager(user):
    if not user.is_authenticated or not user.email:
        return None

    return Manager.objects.filter(email__iexact=user.email).first()


def get_user_worker(user):
    if not user.is_authenticated or not user.email:
        return None

    return Worker.objects.filter(email__iexact=user.email).first()


def is_task_overdue(task):
    return task.due_date < timezone.now()


class IsManager(permissions.BasePermission):
    """
    Custom permission to allow only managers to create and delete tasks.
    """

    def has_permission(self, request, view):
        return get_user_manager(request.user) is not None


class IsManagerOrWorker(permissions.BasePermission):
    """
    Custom permission to allow managers or workers to access task endpoints.
    """

    def has_permission(self, request, view):
        return get_user_manager(request.user) is not None or get_user_worker(request.user) is not None


class TaskPermission(permissions.BasePermission):
    """
    Authenticated users can view tasks. Managers can create, update, and delete
    their workers' tasks. Workers can update their own tasks unless overdue.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if view.action in ["list", "retrieve"]:
            return True

        manager = get_user_manager(request.user)
        worker = get_user_worker(request.user)

        if view.action == "create":
            return manager is not None

        if view.action == "destroy":
            return manager is not None

        if view.action in ["update", "partial_update", "update_status"]:
            return manager is not None or worker is not None

        return False

    def has_object_permission(self, request, view, obj):
        if view.action in ["retrieve", "list"]:
            return True

        manager = get_user_manager(request.user)
        if manager is not None:
            return obj.assigned_to.manager_id_id == manager.manager_id

        worker = get_user_worker(request.user)
        if worker is not None and view.action in ["update", "partial_update", "update_status"]:
            return obj.assigned_to_id == worker.worker_id and not is_task_overdue(obj)

        return False


class ManagerViewSet(viewsets.ModelViewSet):
    queryset = Manager.objects.all()
    serializer_class = ManagerSerializer

class WorkerViewSet(viewsets.ModelViewSet):
    queryset = Worker.objects.all()
    serializer_class = WorkerSerializer
    
    @action(detail=True, methods=['get'], url_path='tasks')
    def get_worker_tasks(self, request, pk=None):
        worker = self.get_object()
        tasks = Task.objects.filter(assigned_to=worker)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [TaskPermission]

    def _get_request_manager(self):
        manager = get_user_manager(self.request.user)
        if manager is None:
            raise PermissionDenied("Only managers can perform this action.")
        return manager

    def perform_create(self, serializer):
        manager = self._get_request_manager()
        assigned_to_id = self.request.data.get('assigned_to') or self.request.data.get('assigned_to_id')

        if not assigned_to_id:
            raise ValidationError({"assigned_to": "This field is required."})

        try:
            worker = Worker.objects.get(pk=assigned_to_id)
        except (Worker.DoesNotExist, TypeError, ValueError):
            raise ValidationError({"assigned_to": "Worker does not exist."})

        if worker.manager_id_id != manager.manager_id:
            raise PermissionDenied("Managers can only assign tasks to their own workers.")

        serializer.save(assigned_to=worker)

    def perform_update(self, serializer):
        manager = get_user_manager(self.request.user)
        worker = get_user_worker(self.request.user)
        task = self.get_object()

        if manager is not None:
            assigned_to_id = self.request.data.get('assigned_to') or self.request.data.get('assigned_to_id')
            if assigned_to_id:
                try:
                    assigned_to = Worker.objects.get(pk=assigned_to_id)
                except (Worker.DoesNotExist, TypeError, ValueError):
                    raise ValidationError({"assigned_to": "Worker does not exist."})

                if assigned_to.manager_id_id != manager.manager_id:
                    raise PermissionDenied("Managers can only assign tasks to their own workers.")

                serializer.save(assigned_to=assigned_to)
                return

            serializer.save()
            return

        if worker is not None:
            if task.assigned_to_id != worker.worker_id:
                raise PermissionDenied("Workers can only update their own tasks.")

            if is_task_overdue(task):
                raise PermissionDenied("Workers cannot update overdue tasks.")

            serializer.save()
            return

        raise PermissionDenied("Only managers or workers can update tasks.")

    def perform_destroy(self, instance):
        manager = self._get_request_manager()

        if instance.assigned_to.manager_id_id != manager.manager_id:
            raise PermissionDenied("Managers can only delete tasks assigned to their own workers.")

        instance.delete()
    

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        task = self.get_object()
        new_status = request.data.get('status')

        if new_status is None:
            return Response({"error": "Status field is required."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TaskSerializer(task, data={'status': new_status}, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
