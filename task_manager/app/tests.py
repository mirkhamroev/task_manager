from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Manager, Task, Worker


class TaskPermissionTests(APITestCase):
    def setUp(self):
        self.manager = Manager.objects.create(
            first_name="Mina",
            last_name="Manager",
            email="manager@example.com",
            dept="Engineering",
        )
        self.worker = Worker.objects.create(
            first_name="Wally",
            last_name="Worker",
            email="worker@example.com",
            dept="Engineering",
            manager_id=self.manager,
            role_title="Developer",
        )
        self.other_manager = Manager.objects.create(
            first_name="Other",
            last_name="Manager",
            email="other-manager@example.com",
            dept="Design",
        )
        self.other_worker = Worker.objects.create(
            first_name="Other",
            last_name="Worker",
            email="other-worker@example.com",
            dept="Design",
            manager_id=self.other_manager,
            role_title="Designer",
        )
        self.task = Task.objects.create(
            title="Build API",
            description="Finish task permissions",
            assigned_to=self.worker,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.overdue_task = Task.objects.create(
            title="Old task",
            description="This task is overdue",
            assigned_to=self.worker,
            due_date=timezone.now() - timedelta(days=1),
        )

        self.viewer_user = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="password",
        )
        self.manager_user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="password",
        )
        self.worker_user = User.objects.create_user(
            username="worker",
            email="worker@example.com",
            password="password",
        )

    def test_authenticated_user_can_view_tasks(self):
        self.client.force_authenticate(user=self.viewer_user)

        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_user_cannot_view_tasks(self):
        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_can_create_task_for_own_worker(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.post(
            "/api/tasks/",
            {
                "title": "New task",
                "description": "Create this task",
                "assigned_to_id": self.worker.worker_id,
                "due_date": (timezone.now() + timedelta(days=2)).isoformat(),
                "status": "Pending",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_manager_cannot_delete_other_managers_task(self):
        self.client.force_authenticate(user=self.manager_user)
        other_task = Task.objects.create(
            title="Other task",
            description="Belongs to another manager",
            assigned_to=self.other_worker,
            due_date=timezone.now() + timedelta(days=1),
        )

        response = self.client.delete(f"/api/tasks/{other_task.task_id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_worker_can_update_own_task(self):
        self.client.force_authenticate(user=self.worker_user)

        response = self.client.patch(
            f"/api/tasks/{self.task.task_id}/",
            {"status": "In Progress"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "In Progress")

    def test_worker_cannot_update_overdue_task(self):
        self.client.force_authenticate(user=self.worker_user)

        response = self.client.patch(
            f"/api/tasks/{self.overdue_task.task_id}/",
            {"status": "Completed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
