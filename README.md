# 📋 Task Manager — Distributed Task Management System

A scalable backend system built with **Django 6** and **Django REST Framework** that tracks organizational work across a strict hierarchy: **Managers → Workers → Tasks**. It features JWT authentication, role-based permissions, and automated background scheduling via Celery + Redis.

```
              ┌─────────────┐
              │   Manager   │  (owns workers, assigns tasks)
              └──────┬──────┘
                     │ 1:N
              ┌──────▼──────┐
              │   Worker    │  (executes tasks, updates status)
              └──────┬──────┘
                     │ 1:N
              ┌──────▼──────┐
              │    Task     │  (Pending → In Progress → Completed)
              └─────────────┘
```

### Tech Stack at a Glance

| Layer | Technology |
|---|---|
| Backend | Python 3.13 · Django 6.0.6 |
| API | Django REST Framework 3.17 (ModelViewSets) |
| Auth | JWT via `djangorestframework-simplejwt` |
| Async | Celery 5.6 + Celery Beat |
| Broker | Redis 7 |
| Database | SQLite (local dev) · PostgreSQL 16 (Docker) |
| Server | Gunicorn (production) · Django dev server (local) |

---

## 🚀 Quick Start

You have **two ways** to run this project. Pick whichever fits your setup.

### Option A — Docker (Recommended)

> This spins up **everything** (Django, PostgreSQL, Redis, Celery) in one command.

```bash
# 1. Clone the repo
git clone <repo-url> && cd task_manager

# 2. Create your environment file
cp .env.example .env

# 3. Build and launch all services
docker compose up --build -d

# 4. Open in browser
#    Swagger UI → http://localhost:8000/
#    Admin      → http://localhost:8000/admin/  (admin / admin123)
#    API root   → http://localhost:8000/api/
```

**Useful Docker commands:**

```bash
docker compose logs -f web            # Django logs
docker compose logs -f celery_worker  # Celery worker logs
docker compose exec web python manage.py test task_manager.app  # Run tests
docker compose down                   # Stop all services
docker compose down -v                # Stop + delete all data
```

### Option B — Local Development (without Docker)

**Prerequisites:** Python 3.13+, Redis server running on port 6379.

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run database migrations
python manage.py migrate

# 4. Create a superuser
python manage.py createsuperuser

# 5. Start Django development server
python manage.py runserver

# 6. (In a separate terminal) Start Celery worker
celery -A task_manager worker --loglevel=info

# 7. (In a separate terminal) Start Celery Beat scheduler
celery -A task_manager beat --loglevel=info
```

---

## 🔐 Authentication — How to Access the API

Every API endpoint (except the Swagger UI page) requires a **JWT Bearer token**.

### Step 1: Get a Token

```bash
curl -X POST http://localhost:8000/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Response:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",   ← use this for API calls (valid 60 min)
  "refresh": "eyJhbGciOiJIUzI1NiIs..."   ← use this to get a new access token (valid 7 days)
}
```

### Step 2: Use the Token

```bash
curl http://localhost:8000/api/tasks/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Step 3: Refresh an Expired Token

```bash
curl -X POST http://localhost:8000/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJhbGciOiJIUzI1NiIs..."}'
```

> **Tip:** Open `http://localhost:8000/` in your browser for an interactive Swagger UI where you can authorize with your token and test all endpoints visually.

---

## 📁 Project Structure — Deep Dive

```
task_manager/                    ← Project root
├── manage.py                    ← Django CLI entry point
├── requirements.txt             ← Python dependencies
├── Dockerfile                   ← Multi-stage Docker image
├── docker-compose.yml           ← Orchestrates 5 services
├── entrypoint.sh                ← Docker startup script
├── .env.example                 ← Environment variable template
├── .dockerignore                ← Files excluded from Docker build
│
└── task_manager/                ← Django project package
    ├── __init__.py              ← Loads Celery on startup
    ├── settings.py              ← All project configuration
    ├── urls.py                  ← URL routing + Swagger UI
    ├── celery.py                ← Celery app initialization
    ├── wsgi.py                  ← WSGI entry (Gunicorn uses this)
    ├── asgi.py                  ← ASGI entry (for async servers)
    │
    └── app/                     ← Main application
        ├── models.py            ← Database models (Manager, Worker, Task, TaskNotification)
        ├── serializer.py        ← DRF serializers (JSON ↔ Model conversion)
        ├── views.py             ← API ViewSets + permissions
        ├── services.py          ← Email notification service layer
        ├── tasks.py             ← Celery background tasks
        ├── admin.py             ← Django admin registrations
        ├── apps.py              ← App configuration
        ├── tests.py             ← Automated test suite
        └── migrations/          ← Database schema migrations
```

---

## 🗄️ Database Models

### How They Connect

```
Manager ──(1:N)──► Worker ──(1:N)──► Task ──(1:N)──► TaskNotification
```

If you delete a Manager, **all** their Workers, Tasks, and TaskNotifications are automatically deleted too (`CASCADE`).

### Manager

| Field | Type | Description |
|---|---|---|
| `manager_id` | AutoField (PK) | Auto-incrementing primary key |
| `first_name` | CharField(50) | Manager's first name |
| `last_name` | CharField(50) | Manager's last name |
| `email` | EmailField (unique) | Used to link Django users to Manager records |
| `dept` | CharField(50) | Department name |

### Worker

| Field | Type | Description |
|---|---|---|
| `worker_id` | AutoField (PK) | Auto-incrementing primary key |
| `first_name` | CharField(50) | Worker's first name |
| `last_name` | CharField(50) | Worker's last name |
| `email` | EmailField (unique) | Used to link Django users to Worker records |
| `dept` | CharField(50) | Department name |
| `manager_id` | ForeignKey → Manager | Which manager this worker reports to |
| `role_title` | CharField(50) | Job title (e.g., "Developer", "Designer") |

### Task

| Field | Type | Description |
|---|---|---|
| `task_id` | AutoField (PK) | Auto-incrementing primary key |
| `title` | CharField(100) | Short task title |
| `description` | TextField | Detailed task description |
| `assigned_to` | ForeignKey → Worker | Which worker is responsible |
| `due_date` | DateTimeField | Deadline (timezone-aware) |
| `status` | CharField(20) | One of: `Pending`, `In Progress`, `Completed` |

### TaskNotification

Tracks which reminder emails have been sent (prevents duplicate emails):

| Field | Type | Description |
|---|---|---|
| `task` | ForeignKey → Task | Which task this notification is for |
| `notification_type` | CharField(30) | `one_month`, `one_week`, `one_day`, `one_hour`, or `manager_due` |
| `sent_at` | DateTimeField | When the notification was sent (auto-set) |

A unique constraint on `(task, notification_type)` ensures each reminder type is sent only once per task.

---

## 🌐 API Endpoints

All endpoints are under `/api/` and require JWT authentication.

### Managers — `/api/managers/`

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/managers/` | List all managers |
| `POST` | `/api/managers/` | Create a new manager |
| `GET` | `/api/managers/{id}/` | Get a specific manager |
| `PUT` | `/api/managers/{id}/` | Update a manager (full) |
| `PATCH` | `/api/managers/{id}/` | Update a manager (partial) |
| `DELETE` | `/api/managers/{id}/` | Delete a manager |

### Workers — `/api/workers/`

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/workers/` | List all workers |
| `POST` | `/api/workers/` | Create a new worker |
| `GET` | `/api/workers/{id}/` | Get a specific worker |
| `PUT` | `/api/workers/{id}/` | Update a worker (full) |
| `PATCH` | `/api/workers/{id}/` | Update a worker (partial) |
| `DELETE` | `/api/workers/{id}/` | Delete a worker |
| `GET` | `/api/workers/{id}/tasks/` | **List all tasks assigned to this worker** |

### Tasks — `/api/tasks/`

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/tasks/` | List all tasks |
| `POST` | `/api/tasks/` | Create a task (managers only) |
| `GET` | `/api/tasks/{id}/` | Get a specific task |
| `PUT` | `/api/tasks/{id}/` | Update a task |
| `PATCH` | `/api/tasks/{id}/` | Partial update a task |
| `DELETE` | `/api/tasks/{id}/` | Delete a task (managers only) |
| `PATCH` | `/api/tasks/{id}/update-status/` | **Quick status update** |

### Authentication

| Method | URL | Description |
|---|---|---|
| `POST` | `/token/` | Get access + refresh tokens |
| `POST` | `/token/refresh/` | Refresh an expired access token |

### Documentation

| URL | Description |
|---|---|
| `/` or `/swagger/` | Interactive Swagger UI |
| `/schema/` | Raw OpenAPI JSON schema |
| `/admin/` | Django admin panel |

---

## 🔒 Permission System

The system links Django user accounts to Manager/Worker records **by matching email addresses**.

| Action | Who Can Do It | Extra Rules |
|---|---|---|
| **View** tasks | Any authenticated user | — |
| **Create** tasks | Managers only | Can only assign to their own workers |
| **Update** tasks | Managers + Workers | Managers: own workers' tasks only. Workers: own tasks only, and task must NOT be overdue |
| **Delete** tasks | Managers only | Can only delete their own workers' tasks |

**How it works:** When you log in as `admin@example.com`, the system checks if that email exists in the `Manager` table or the `Worker` table, and grants permissions accordingly.

---

## ⚙️ Background Tasks (Celery)

Two scheduled tasks run **every hour** (at minute 0):

### 1. `notify_overdue_tasks`
Scans for all incomplete tasks past their `due_date` and logs warnings with full details (task title, worker name, manager name).

### 2. `send_task_due_notifications`
Sends email reminders to workers at four intervals before a task is due:

| Interval | Notification Type | Recipient |
|---|---|---|
| 30 days before | `one_month` | Worker |
| 7 days before | `one_week` | Worker |
| 1 day before | `one_day` | Worker |
| 1 hour before | `one_hour` | Worker |
| Due date reached | `manager_due` | **Manager** |

Each notification is sent only once — tracked via the `TaskNotification` model.

---

## 🐳 Docker Architecture

```
docker compose up --build -d
```

This starts **5 containers**:

```
┌──────────────┐      ┌───────────────┐      ┌─────────────┐
│  PostgreSQL  │◄─────│  Django Web   │─────►│    Redis     │
│    :5432     │      │   (Gunicorn)  │      │    :6379     │
│              │      │    :8000      │      │              │
└──────────────┘      └───────────────┘      └──────┬──────┘
       ▲                                            │
       │              ┌───────────────┐             │
       ├──────────────│ Celery Worker │◄────────────┤
       │              │ (concurrency=2)│             │
       │              └───────────────┘             │
       │              ┌───────────────┐             │
       └──────────────│  Celery Beat  │◄────────────┘
                      │  (scheduler)  │
                      └───────────────┘
```

| Service | Image | Purpose |
|---|---|---|
| `db` | `postgres:16-alpine` | Persistent relational database |
| `redis` | `redis:7-alpine` | Message broker for Celery |
| `web` | Custom (Dockerfile) | Django app served by Gunicorn |
| `celery_worker` | Custom (Dockerfile) | Executes background tasks |
| `celery_beat` | Custom (Dockerfile) | Schedules periodic tasks |

### Startup Flow

1. `db` and `redis` start first (health checks ensure readiness)
2. `entrypoint.sh` runs: waits for DB → runs migrations → collects static files → creates superuser
3. Gunicorn starts serving on port 8000
4. Celery worker and beat connect to Redis and begin processing

---

## 🧪 Running Tests

```bash
# Docker
docker compose exec web python manage.py test task_manager.app

# Local
python manage.py test task_manager.app
```

The test suite (`task_manager/app/tests.py`) covers:

| Test | What It Verifies |
|---|---|
| `test_authenticated_user_can_view_tasks` | Logged-in users can list tasks |
| `test_unauthenticated_user_cannot_view_tasks` | Anonymous requests get `401` |
| `test_manager_can_create_task_for_own_worker` | Managers can assign tasks to their workers |
| `test_manager_cannot_delete_other_managers_task` | Cross-manager deletion is blocked (`403`) |
| `test_worker_can_update_own_task` | Workers can change status on their tasks |
| `test_worker_cannot_update_overdue_task` | Overdue tasks are frozen for workers (`403`) |

---

## ⚙️ Environment Variables

All config is controlled via environment variables (with safe defaults for local dev). Copy `.env.example` to `.env` to customize:

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `1` | Set to `0` in production |
| `SECRET_KEY` | insecure dev key | **Change this in production!** |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |
| `POSTGRES_DB` | `task_manager` | Database name |
| `POSTGRES_USER` | `task_user` | Database user |
| `POSTGRES_PASSWORD` | `task_password` | Database password |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Auto-created admin username |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Auto-created admin email |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123` | Auto-created admin password |
| `WEB_PORT` | `8000` | Host port for Django |

---

## 📝 Example API Workflow

Here's a complete workflow to get familiar with the system:

```bash
# 1. Get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access'])")

# 2. Create a Manager
curl -X POST http://localhost:8000/api/managers/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Smith","email":"admin@example.com","dept":"Engineering"}'

# 3. Create a Worker under that Manager
curl -X POST http://localhost:8000/api/workers/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Bob","last_name":"Jones","email":"bob@example.com","dept":"Engineering","manager_id":1,"role_title":"Developer"}'

# 4. Assign a Task to the Worker
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Build login page","description":"Create the auth UI","assigned_to_id":1,"due_date":"2026-07-01T12:00:00Z","status":"Pending"}'

# 5. Update task status
curl -X PATCH http://localhost:8000/api/tasks/1/update-status/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"In Progress"}'

# 6. View all tasks for a specific worker
curl http://localhost:8000/api/workers/1/tasks/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🗺️ Future Roadmap

- **RBAC**: Fine-grained role-based access control at the view level
- **Email Notifications**: Connect SMTP/SMS providers to Celery pipeline
- **Collaborative Tasks**: Many-to-many worker-task assignments
- **Frontend Dashboard**: Web UI to interact with these API endpoints
