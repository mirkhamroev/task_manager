import logging
from datetime import timedelta

from celery import shared_task
from django.db import IntegrityError
from django.utils import timezone

from .models import Status, Task, TaskNotification
from .services import send_manager_task_due_email, send_worker_task_reminder

logger = logging.getLogger(__name__)

REMINDER_SCHEDULE = [
    (TaskNotification.ONE_MONTH, "1 month", timedelta(days=30)),
    (TaskNotification.ONE_WEEK, "1 week", timedelta(weeks=1)),
    (TaskNotification.ONE_DAY, "1 day", timedelta(days=1)),
    (TaskNotification.ONE_HOUR, "1 hour", timedelta(hours=1)),
]
REMINDER_LOOKAHEAD = timedelta(hours=1)


def _record_notification(task, notification_type):
    try:
        TaskNotification.objects.create(
            task=task,
            notification_type=notification_type,
        )
    except IntegrityError:
        return False

    return True


@shared_task
def notify_overdue_tasks():
    now = timezone.now()
    overdue_tasks = (
        Task.objects
        .select_related("assigned_to", "assigned_to__user", "assigned_to__manager", "assigned_to__manager__user")
        .filter(due_date__lt=now)
        .exclude(status=Status.COMPLETED.value)
    )
    overdue_count = overdue_tasks.count()

    logger.warning("Found %s overdue incomplete task(s) at %s.", overdue_count, now.isoformat())

    for task in overdue_tasks:
        worker = task.assigned_to
        worker_user = worker.user
        manager = worker.manager
        manager_user = manager.user

        logger.warning(
            "Overdue task alert: task_id=%s title=%r due_date=%s status=%r "
            "worker=%s %s <%s> manager=%s %s <%s>",
            task.task_id,
            task.title,
            task.due_date.isoformat(),
            task.status,
            worker_user.first_name,
            worker_user.last_name,
            worker_user.email,
            manager_user.first_name,
            manager_user.last_name,
            manager_user.email,
        )

    return {
        "checked_at": now.isoformat(),
        "overdue_count": overdue_count,
    }


@shared_task
def send_task_due_notifications():
    now = timezone.now()
    incomplete_tasks = (
        Task.objects
        .select_related("assigned_to", "assigned_to__user", "assigned_to__manager", "assigned_to__manager__user")
        .exclude(status=Status.COMPLETED.value)
    )
    sent_notifications = 0

    for notification_type, reminder_label, before_due in REMINDER_SCHEDULE:
        reminder_window_start = now + before_due
        reminder_window_end = reminder_window_start + REMINDER_LOOKAHEAD
        reminder_tasks = incomplete_tasks.filter(
            due_date__gt=reminder_window_start,
            due_date__lte=reminder_window_end,
        )

        for task in reminder_tasks:
            if not _record_notification(task, notification_type):
                continue

            sent_notifications += send_worker_task_reminder(task, reminder_label)

    due_tasks = incomplete_tasks.filter(due_date__lte=now)

    for task in due_tasks:
        if not _record_notification(task, TaskNotification.MANAGER_DUE):
            continue

        sent_notifications += send_manager_task_due_email(task)

    return {
        "checked_at": now.isoformat(),
        "sent_notifications": sent_notifications,
    }
