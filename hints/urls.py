from django.urls import path
from . import views

urlpatterns = [
    path("vocab/<int:vocab_id>/", views.vocab_hints, name="vocab_hints"),
    path("vocab/<int:vocab_id>/use/", views.use_quiz_hint, name="use_quiz_hint"),
    path("usage/today/", views.hint_usage_today, name="hint_usage_today"),
]
