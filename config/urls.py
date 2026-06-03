"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import re

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.shortcuts import redirect
from django.views.static import serve


def _redirect_to_course(request, model_name: str, rest: str = ""):
    # Preserve any trailing path (e.g., add/, <pk>/change/)
    suffix = ("/" + rest) if rest else ""
    return redirect(f"/admin/course/{model_name}{suffix}")

urlpatterns = [
    # Legacy admin paths for moved models -> redirect to new `course` admin
    path('admin/core/level/<path:rest>/', lambda r, rest: _redirect_to_course(r, 'level', rest)),
    path('admin/core/level/', lambda r: _redirect_to_course(r, 'level')),
    path('admin/core/unit/<path:rest>/', lambda r, rest: _redirect_to_course(r, 'unit', rest)),
    path('admin/core/unit/', lambda r: _redirect_to_course(r, 'unit')),
    path('admin/core/vocabularyitem/<path:rest>/', lambda r, rest: _redirect_to_course(r, 'vocabularyitem', rest)),
    path('admin/core/vocabularyitem/', lambda r: _redirect_to_course(r, 'vocabularyitem')),
    path('admin/core/grammarcontent/<path:rest>/', lambda r, rest: _redirect_to_course(r, 'grammarcontent', rest)),
    path('admin/core/grammarcontent/', lambda r: _redirect_to_course(r, 'grammarcontent')),

    path('admin/', admin.site.urls),
    path("api/admin/", include("administration.urls")),
    path("", include("core.urls")),
]

if settings.MEDIA_URL and settings.MEDIA_ROOT:
    # Serve uploaded media (e.g., profile pictures) even when DEBUG=False.
    # Prefer a real web server/CDN for large deployments.
    media_prefix = settings.MEDIA_URL.lstrip("/")
    urlpatterns += [
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(media_prefix),
            serve,
            kwargs={"document_root": settings.MEDIA_ROOT},
        )
    ]
