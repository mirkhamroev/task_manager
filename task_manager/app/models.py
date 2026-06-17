from django.contrib.auth.models import AbstractUser
from django.db import models
import enum


class Status(enum.Enum):
    PENDING = 'Pending'
    IN_PROGRESS = 'In Progress'
    COMPLETED = 'Completed'


class CustomUser(AbstractUser):
    """
    Custom user model that adds a role field to distinguish managers from workers.
    All authentication (login, JWT tokens) goes through this single model.
    """

    ROLE_MANAGER = 'manager'
    ROLE_WORKER = 'worker'
    ROLE_CHOICES = [
        (ROLE_MANAGER, 'Manager'),
        (ROLE_WORKER, 'Worker'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_worker(self):
        return self.role == self.ROLE_WORKER


class Manager(models.Model):
    """
    Manager profile linked to a CustomUser.
    Each manager can have multiple workers.
    """

    manager_id = models.AutoField(primary_key=True, unique=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='manager_profile',
    )
    dept = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.dept}"


class Worker(models.Model):
    """
    Worker profile linked to a CustomUser.
    Each worker is assigned to a manager.
    """

    worker_id = models.AutoField(primary_key=True, unique=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='worker_profile',
    )
    dept = models.CharField(max_length=50)
    manager = models.ForeignKey(
        Manager,
        on_delete=models.CASCADE,
        related_name='workers',
    )
    role_title = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.role_title}"


class Task(models.Model):
    """
    Task model to store task information.
    task_id: Auto-incrementing primary key for the task.
    assigned_to: Foreign key to the Worker model, indicating which worker is assigned the task.
    due_date: Date and time when the task is due.
    status: Current status of the task (Pending, In Progress, Completed).
    """

    task_id = models.AutoField(primary_key=True, unique=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    assigned_to = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='tasks')
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, default=Status.PENDING.value)

    def __str__(self):
        return self.title


class TaskNotification(models.Model):
    """
    Tracks which email notifications have already been sent for a task.
    """

    ONE_MONTH = "one_month"
    ONE_WEEK = "one_week"
    ONE_DAY = "one_day"
    ONE_HOUR = "one_hour"
    MANAGER_DUE = "manager_due"

    NOTIFICATION_TYPES = [
        (ONE_MONTH, "One month before due date"),
        (ONE_WEEK, "One week before due date"),
        (ONE_DAY, "One day before due date"),
        (ONE_HOUR, "One hour before due date"),
        (MANAGER_DUE, "Manager due-date alert"),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "notification_type"],
                name="unique_task_notification_type",
            )
        ]
