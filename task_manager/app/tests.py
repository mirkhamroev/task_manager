from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Manager, Task, Worker, Status

User = get_user_model()


class AuthTests(APITestCase):
    """Tests for registration and login endpoints."""

    def test_register_manager(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "mgr1",
                "password": "securepass123",
                "email": "mgr1@example.com",
                "first_name": "Mina",
                "last_name": "Manager",
                "role": "manager",
                "dept": "Engineering",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "manager")
        self.assertTrue(User.objects.filter(username="mgr1").exists())
        self.assertTrue(Manager.objects.filter(user__username="mgr1").exists())

    def test_register_worker_requires_manager(self):
        # Create a manager first
        mgr_user = User.objects.create_user(
            username="mgr", password="pass", email="mgr@example.com", role="manager"
        )
        mgr = Manager.objects.create(user=mgr_user, dept="Eng")

        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "wrk1",
                "password": "securepass123",
                "email": "wrk1@example.com",
                "first_name": "Wally",
                "last_name": "Worker",
                "role": "worker",
                "dept": "Engineering",
                "manager_id": mgr.pk,
                "role_title": "Developer",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "worker")

    def test_register_worker_without_manager_fails(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "wrk_fail",
                "password": "securepass123",
                "email": "wrkfail@example.com",
                "first_name": "Bad",
                "last_name": "Worker",
                "role": "worker",
                "dept": "Engineering",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_token_with_role(self):
        User.objects.create_user(
            username="loginuser", password="pass123", email="login@example.com", role="manager"
        )
        response = self.client.post(
            "/api/auth/login/",
            {"username": "loginuser", "password": "pass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["role"], "manager")

    def test_login_wrong_password(self):
        User.objects.create_user(
            username="loginuser2", password="pass123", email="login2@example.com", role="worker"
        )
        response = self.client.post(
            "/api/auth/login/",
            {"username": "loginuser2", "password": "wrongpass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_duplicate_username_rejected(self):
        User.objects.create_user(
            username="dupe", password="pass", email="dupe@example.com", role="manager"
        )
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "dupe",
                "password": "pass123",
                "email": "new@example.com",
                "first_name": "A",
                "last_name": "B",
                "role": "manager",
                "dept": "X",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_endpoint(self):
        user = User.objects.create_user(
            username="profuser", password="pass", email="prof@example.com", role="manager"
        )
        Manager.objects.create(user=user, dept="Eng")
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "manager")
        self.assertIsNotNone(response.data["manager_profile"])


class TaskPermissionTests(APITestCase):
    def setUp(self):
        # Create manager user + profile
        self.manager_user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="password",
            first_name="Mina",
            last_name="Manager",
            role="manager",
        )
        self.manager = Manager.objects.create(user=self.manager_user, dept="Engineering")

        # Create worker user + profile
        self.worker_user = User.objects.create_user(
            username="worker",
            email="worker@example.com",
            password="password",
            first_name="Wally",
            last_name="Worker",
            role="worker",
        )
        self.worker = Worker.objects.create(
            user=self.worker_user,
            dept="Engineering",
            manager=self.manager,
            role_title="Developer",
        )

        # Create another manager + worker (for cross-team permission tests)
        self.other_manager_user = User.objects.create_user(
            username="other_manager",
            email="other-manager@example.com",
            password="password",
            first_name="Other",
            last_name="Manager",
            role="manager",
        )
        self.other_manager = Manager.objects.create(user=self.other_manager_user, dept="Design")

        self.other_worker_user = User.objects.create_user(
            username="other_worker",
            email="other-worker@example.com",
            password="password",
            first_name="Other",
            last_name="Worker",
            role="worker",
        )
        self.other_worker = Worker.objects.create(
            user=self.other_worker_user,
            dept="Design",
            manager=self.other_manager,
            role_title="Designer",
        )

        # Create tasks
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

    def test_unauthenticated_user_cannot_view_tasks(self):
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_can_view_own_team_tasks(self):
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Manager should see only their team's tasks
        task_ids = [t["task_id"] for t in response.data]
        self.assertIn(self.task.task_id, task_ids)

    def test_worker_can_view_own_tasks(self):
        self.client.force_authenticate(user=self.worker_user)
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task_ids = [t["task_id"] for t in response.data]
        self.assertIn(self.task.task_id, task_ids)

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

    def test_worker_cannot_create_task(self):
        self.client.force_authenticate(user=self.worker_user)
        response = self.client.post(
            "/api/tasks/",
            {
                "title": "Rogue task",
                "description": "Workers cannot create",
                "assigned_to_id": self.worker.worker_id,
                "due_date": (timezone.now() + timedelta(days=2)).isoformat(),
                "status": "Pending",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete_other_managers_task(self):
        """Other team's tasks are invisible (404) due to scoped queryset — better than 403."""
        self.client.force_authenticate(user=self.manager_user)
        other_task = Task.objects.create(
            title="Other task",
            description="Belongs to another manager",
            assigned_to=self.other_worker,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.delete(f"/api/tasks/{other_task.task_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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

    def test_worker_can_complete_own_task(self):
        self.client.force_authenticate(user=self.worker_user)
        response = self.client.patch(
            f"/api/tasks/{self.task.task_id}/complete/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Status.COMPLETED.value)

    def test_manager_can_recover_completed_task(self):
        self.task.status = Status.COMPLETED.value
        self.task.save()

        self.client.force_authenticate(user=self.manager_user)
        response = self.client.patch(
            f"/api/tasks/{self.task.task_id}/recover/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Status.IN_PROGRESS.value)

    def test_worker_cannot_recover_task(self):
        self.task.status = Status.COMPLETED.value
        self.task.save()

        self.client.force_authenticate(user=self.worker_user)
        response = self.client.patch(
            f"/api/tasks/{self.task.task_id}/recover/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_recover_non_completed_task(self):
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.patch(
            f"/api/tasks/{self.task.task_id}/recover/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
