from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Manager, Worker, Task, TaskNotification


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "first_name", "last_name", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ("manager_id", "get_username", "get_email", "dept")

    @admin.display(description="Username")
    def get_username(self, obj):
        return obj.user.username

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("worker_id", "get_username", "get_email", "dept", "manager", "role_title")

    @admin.display(description="Username")
    def get_username(self, obj):
        return obj.user.username

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("task_id", "title", "assigned_to", "status", "due_date")


@admin.register(TaskNotification)
class TaskNotificationAdmin(admin.ModelAdmin):
    list_display = ("task", "notification_type", "sent_at")
