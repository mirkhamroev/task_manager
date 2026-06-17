import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Task

logger = logging.getLogger(__name__)


def _worker_reminder_subject(task, reminder_label):
    return f"Task reminder: {task.title} is due in {reminder_label}"


def _worker_reminder_message(task, reminder_label):
    worker = task.assigned_to
    user = worker.user
    return (
        f"Hello {user.first_name},\n\n"
        f"This is a reminder that your task is due in {reminder_label}.\n\n"
        f"Task: {task.title}\n"
        f"Description: {task.description}\n"
        f"Due date: {timezone.localtime(task.due_date).strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Status: {task.status}\n\n"
        "Please update the task before the deadline."
    )


def _manager_due_subject(task):
    return f"Task due-date reached: {task.title}"


def _manager_due_message(task):
    worker = task.assigned_to
    manager = worker.manager
    manager_user = manager.user
    worker_user = worker.user
    return (
        f"Hello {manager_user.first_name},\n\n"
        "A task assigned to one of your workers has reached its due date.\n\n"
        f"Task: {task.title}\n"
        f"Description: {task.description}\n"
        f"Worker: {worker_user.first_name} {worker_user.last_name} <{worker_user.email}>\n"
        f"Due date: {timezone.localtime(task.due_date).strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Status: {task.status}\n"
    )


def send_worker_task_reminder(task, reminder_label):
    """
    Sends a reminder email to the worker assigned to a task.
    """

    worker_email = task.assigned_to.user.email
    if not worker_email:
        logger.warning("Task %s worker has no email address.", task.task_id)
        return 0

    return send_mail(
        subject=_worker_reminder_subject(task, reminder_label),
        message=_worker_reminder_message(task, reminder_label),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[worker_email],
        fail_silently=False,
    )


def send_manager_task_due_email(task):
    """
    Sends an email to the manager when a task reaches its due date.
    """

    manager = task.assigned_to.manager
    manager_email = manager.user.email
    if not manager_email:
        logger.warning("Task %s manager has no email address.", task.task_id)
        return 0

    return send_mail(
        subject=_manager_due_subject(task),
        message=_manager_due_message(task),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[manager_email],
        fail_silently=False,
    )
