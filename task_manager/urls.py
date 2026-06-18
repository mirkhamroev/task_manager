"""
URL configuration for task_manager project.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view
from rest_framework_simplejwt.views import TokenRefreshView

from task_manager.app.views import (
    ManagerViewSet,
    TaskViewSet,
    WorkerViewSet,
    RegisterView,
    CustomTokenObtainPairView,
    ProfileView,
)


class PublicAPIRootRouter(DefaultRouter):
    """Root view that allows anonymous access."""
    APIRootView = type(
        "APIRootView",
        (DefaultRouter.APIRootView,),
        {"permission_classes": [AllowAny]},
    )


router = PublicAPIRootRouter()
router.register(r"managers", ManagerViewSet, basename="manager")
router.register(r"workers", WorkerViewSet, basename="worker")
router.register(r"tasks", TaskViewSet, basename="task")

schema_view = get_schema_view(
    title="Task Manager API",
    description="API documentation for managers, workers, tasks, and authentication.",
    version="1.0.0",
    public=True,
    permission_classes=[AllowAny],
    renderer_classes=[JSONOpenAPIRenderer],
)


def swagger_ui(request):
    html = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>Task Manager API</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
      </head>
      <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
          fetch("/schema/")
            .then((response) => response.json())
            .then((schema) => {
              schema.components = schema.components || {};
              schema.components.securitySchemes = schema.components.securitySchemes || {};
              schema.components.securitySchemes.bearerAuth = {
                type: "http",
                scheme: "bearer",
                bearerFormat: "JWT"
              };
              schema.security = [{ bearerAuth: [] }];

              SwaggerUIBundle({
                spec: schema,
                dom_id: "#swagger-ui",
                deepLinking: true,
                persistAuthorization: true,
                presets: [
                  SwaggerUIBundle.presets.apis,
                  SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout"
              });
            });
        </script>
      </body>
    </html>
    """
    return HttpResponse(html)


urlpatterns = [
    path("", swagger_ui, name="swagger-ui"),
    path("swagger/", swagger_ui, name="swagger-ui-alt"),
    path("schema/", schema_view, name="openapi-schema"),
    path("admin/", admin.site.urls),

    # Resource APIs
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),

    # Auth endpoints
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="auth-login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("api/auth/profile/", ProfileView.as_view(), name="auth-profile"),
]
