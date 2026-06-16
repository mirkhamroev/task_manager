from django.db import models
import enum

# Create your models here.
class Status(enum.Enum):
    PENDING = 'Pending'
    IN_PROGRESS = 'In Progress'
    COMPLETED = 'Completed'

class Manager(models.Model):
    """
    Manager model to store manager information. Each manager can have multiple workers.
    manager_id: Auto-incrementing primary key for the manager.
    """
    
    manager_id = models.AutoField(primary_key=True, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    dept = models.CharField(max_length=50)

class Worker(models.Model):
    """
    Worker model to store worker information. Each worker is assigned to a manager.
    worker_id: Auto-incrementing primary key for the worker.
    manager_id: Foreign key to the Manager model, indicating which manager the worker reports to.
    """

    worker_id = models.AutoField(primary_key=True, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    dept = models.CharField(max_length=50)
    manager_id = models.ForeignKey(Manager, on_delete=models.CASCADE)
    role_title = models.CharField(max_length=50)

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
    assigned_to = models.ForeignKey(Worker, on_delete=models.CASCADE)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, default=Status.PENDING.value)


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
