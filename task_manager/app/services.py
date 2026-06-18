import logging

from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
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
        auth_password=settings.EMAIL_HOST_PASSWORD,
        auth_user=settings.EMAIL_HOST_USER,
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
        auth_password=settings.EMAIL_HOST_PASSWORD,
        auth_user=settings.EMAIL_HOST_USER,
        fail_silently=False,
    )


def send_worker_task_assigned_email(task):
    """
    Sends an email to the worker when a new task is assigned to them.
    """

    worker_email = task.assigned_to.user.email
    if not worker_email:
        logger.warning("Task %s worker has no email address.", task.task_id)
        return 0

    worker_user = task.assigned_to.user
    manager_user = task.assigned_to.manager.user
    subject = f"New task assigned: {task.title}"
    message = (
        f"Hello {worker_user.first_name},\n\n"
        f"You have been assigned a new task by {manager_user.get_full_name()}.\n\n"
        f"Task: {task.title}\n"
        f"Description: {task.description}\n"
        f"Due date: {timezone.localtime(task.due_date).strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Status: {task.status}\n\n"
        "Please review the task and start working on it."
    )

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[worker_email],
        auth_password=settings.EMAIL_HOST_PASSWORD,
        auth_user=settings.EMAIL_HOST_USER,
        fail_silently=False,
    )


def send_worker_overdue_email(task):
    """
    Sends an email to the worker when their task is overdue.
    """

    worker_email = task.assigned_to.user.email
    if not worker_email:
        logger.warning("Task %s worker has no email address.", task.task_id)
        return 0

    worker_user = task.assigned_to.user
    subject = f"OVERDUE: {task.title}"
    message = (
        f"Hello {worker_user.first_name},\n\n"
        f"Your task is OVERDUE and has not been completed.\n\n"
        f"Task: {task.title}\n"
        f"Description: {task.description}\n"
        f"Due date: {timezone.localtime(task.due_date).strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Status: {task.status}\n\n"
        "Please complete this task as soon as possible or contact your manager."
    )

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[worker_email],
        auth_password=settings.EMAIL_HOST_PASSWORD,
        auth_user=settings.EMAIL_HOST_USER,
        fail_silently=False,
    )


def send_manager_overdue_email(task):
    """
    Sends an email to the manager when a worker's task is overdue.
    """

    manager = task.assigned_to.manager
    manager_email = manager.user.email
    if not manager_email:
        logger.warning("Task %s manager has no email address.", task.task_id)
        return 0

    manager_user = manager.user
    worker_user = task.assigned_to.user
    subject = f"OVERDUE: {task.title} — worker {worker_user.get_full_name()}"
    message = (
        f"Hello {manager_user.first_name},\n\n"
        f"A task assigned to one of your workers is OVERDUE.\n\n"
        f"Task: {task.title}\n"
        f"Description: {task.description}\n"
        f"Worker: {worker_user.first_name} {worker_user.last_name} <{worker_user.email}>\n"
        f"Due date: {timezone.localtime(task.due_date).strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"Status: {task.status}\n\n"
        "Please follow up with the worker to ensure this task is completed."
    )

    return send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[manager_email],
        auth_password=settings.EMAIL_HOST_PASSWORD,
        auth_user=settings.EMAIL_HOST_USER,
        fail_silently=False,
    )
