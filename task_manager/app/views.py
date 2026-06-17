from rest_framework import viewsets, status, permissions, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone

from .models import Task, Worker, Manager, Status
from .serializer import TaskSerializer, WorkerSerializer, ManagerSerializer
from .auth_serializers import (
    RegisterSerializer,
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
)


# ============================================================================
# Auth views
# ============================================================================

class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Creates a new user account with a Manager or Worker profile.
    Open to all (no token required).
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": f"{user.get_role_display()} registered successfully.",
                "user_id": user.pk,
                "username": user.username,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Returns access + refresh JWT tokens with the user's role embedded.
    """

    serializer_class = CustomTokenObtainPairSerializer


class ProfileView(generics.RetrieveAPIView):
    """
    GET /api/auth/profile/
    Returns the authenticated user's profile information.
    """

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ============================================================================
# Permission helpers
# ============================================================================

def _get_manager_profile(user):
    """Return the Manager profile for the user, or None."""
    if user.is_manager and hasattr(user, "manager_profile"):
        return user.manager_profile
    return None


def _get_worker_profile(user):
    """Return the Worker profile for the user, or None."""
    if user.is_worker and hasattr(user, "worker_profile"):
        return user.worker_profile
    return None


def _is_task_overdue(task):
    return task.due_date < timezone.now()


# ============================================================================
# Custom permissions
# ============================================================================

class IsManager(permissions.BasePermission):
    """Custom permission to allow only managers."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_manager


class TaskPermission(permissions.BasePermission):
    """
    Authenticated users can view tasks.
    Managers can create, update, and delete their workers' tasks.
    Workers can update their own tasks unless overdue.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if view.action in ["list", "retrieve"]:
            return True

        if view.action == "create":
            return request.user.is_manager

        if view.action == "destroy":
            return request.user.is_manager

        if view.action in ["update", "partial_update", "update_status", "complete_task"]:
            return request.user.is_manager or request.user.is_worker

        if view.action == "recover_task":
            return request.user.is_manager

        return False

    def has_object_permission(self, request, view, obj):
        if view.action in ["retrieve", "list"]:
            return True

        manager = _get_manager_profile(request.user)
        if manager is not None:
            return obj.assigned_to.manager_id == manager.manager_id

        worker = _get_worker_profile(request.user)
        if worker is not None and view.action in [
            "update", "partial_update", "update_status", "complete_task"
        ]:
            return obj.assigned_to_id == worker.worker_id and not _is_task_overdue(obj)

        return False


# ============================================================================
# Resource viewsets
# ============================================================================

class ManagerViewSet(viewsets.ModelViewSet):
    queryset = Manager.objects.select_related("user").all()
    serializer_class = ManagerSerializer
    permission_classes = [permissions.IsAuthenticated]


class WorkerViewSet(viewsets.ModelViewSet):
    queryset = Worker.objects.select_related("user", "manager", "manager__user").all()
    serializer_class = WorkerSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="tasks")
    def get_worker_tasks(self, request, pk=None):
        worker = self.get_object()
        tasks = Task.objects.filter(assigned_to=worker).select_related("assigned_to__user")
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [TaskPermission]

    def get_queryset(self):
        """
        Scope the task list to the requesting user's context:
        - Managers see tasks assigned to their workers.
        - Workers see only their own tasks.
        - Admins/superusers see everything.
        """
        user = self.request.user
        qs = Task.objects.select_related(
            "assigned_to", "assigned_to__user", "assigned_to__manager", "assigned_to__manager__user"
        )

        if user.is_superuser:
            return qs

        manager = _get_manager_profile(user)
        if manager is not None:
            return qs.filter(assigned_to__manager=manager)

        worker = _get_worker_profile(user)
        if worker is not None:
            return qs.filter(assigned_to=worker)

        return qs.none()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def _get_request_manager(self):
        manager = _get_manager_profile(self.request.user)
        if manager is None:
            raise PermissionDenied("Only managers can perform this action.")
        return manager

    def perform_create(self, serializer):
        manager = self._get_request_manager()
        assigned_to_id = (
            self.request.data.get("assigned_to")
            or self.request.data.get("assigned_to_id")
        )

        if not assigned_to_id:
            raise ValidationError({"assigned_to": "This field is required."})

        try:
            worker = Worker.objects.get(pk=assigned_to_id)
        except (Worker.DoesNotExist, TypeError, ValueError):
            raise ValidationError({"assigned_to": "Worker does not exist."})

        if worker.manager_id != manager.manager_id:
            raise PermissionDenied("Managers can only assign tasks to their own workers.")

        serializer.save(assigned_to=worker)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def perform_update(self, serializer):
        manager = _get_manager_profile(self.request.user)
        worker = _get_worker_profile(self.request.user)
        task = self.get_object()

        if manager is not None:
            assigned_to_id = (
                self.request.data.get("assigned_to")
                or self.request.data.get("assigned_to_id")
            )
            if assigned_to_id:
                try:
                    assigned_to = Worker.objects.get(pk=assigned_to_id)
                except (Worker.DoesNotExist, TypeError, ValueError):
                    raise ValidationError({"assigned_to": "Worker does not exist."})

                if assigned_to.manager_id != manager.manager_id:
                    raise PermissionDenied("Managers can only assign tasks to their own workers.")

                serializer.save(assigned_to=assigned_to)
                return

            serializer.save()
            return

        if worker is not None:
            if task.assigned_to_id != worker.worker_id:
                raise PermissionDenied("Workers can only update their own tasks.")

            if _is_task_overdue(task):
                raise PermissionDenied("Workers cannot update overdue tasks.")

            serializer.save()
            return

        raise PermissionDenied("Only managers or workers can update tasks.")

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def perform_destroy(self, instance):
        manager = self._get_request_manager()

        if instance.assigned_to.manager_id != manager.manager_id:
            raise PermissionDenied("Managers can only delete tasks assigned to their own workers.")

        instance.delete()

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="update-status")
    def update_status(self, request, pk=None):
        """PATCH /api/tasks/{id}/update-status/ — update the status field."""
        task = self.get_object()
        new_status = request.data.get("status")

        if new_status is None:
            return Response(
                {"error": "Status field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TaskSerializer(task, data={"status": new_status}, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["patch"], url_path="complete")
    def complete_task(self, request, pk=None):
        """
        PATCH /api/tasks/{id}/complete/
        Workers mark their own task as Completed.
        """
        task = self.get_object()

        if task.status == Status.COMPLETED.value:
            return Response(
                {"error": "Task is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = Status.COMPLETED.value
        task.save(update_fields=["status"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="recover")
    def recover_task(self, request, pk=None):
        """
        PATCH /api/tasks/{id}/recover/
        Managers reset a completed task back to In Progress.
        """
        task = self.get_object()

        manager = _get_manager_profile(request.user)
        if manager is None:
            raise PermissionDenied("Only managers can recover tasks.")

        if task.assigned_to.manager_id != manager.manager_id:
            raise PermissionDenied("Managers can only recover tasks assigned to their own workers.")

        if task.status != Status.COMPLETED.value:
            return Response(
                {"error": "Only completed tasks can be recovered."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = Status.IN_PROGRESS.value
        task.save(update_fields=["status"])
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)
