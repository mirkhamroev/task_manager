from django.contrib import admin
from .models import Manager, Task, TaskNotification, Worker

# Register your models here.

admin.site.register(Manager)
admin.site.register(Worker)
admin.site.register(Task)
admin.site.register(TaskNotification)
