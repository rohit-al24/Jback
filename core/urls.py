from django.urls import path

from . import auth_views, billing_views, path_views, portal_views, referral_views, review_views, views


urlpatterns = [
    # Portal (HTML)
    path("", portal_views.portal_index, name="portal_index"),
    path("portal/login/", portal_views.portal_login, name="portal_login"),
    path("portal/logout/", portal_views.portal_logout, name="portal_logout"),

    # Shitsumon (HTML)
    path("shitsumon/", portal_views.shitsumon_dashboard, name="shitsumon_dashboard"),
    path("shitsumon/new/", portal_views.shitsumon_create, name="shitsumon_create"),
    path("shitsumon/<str:public_id>/edit/", portal_views.shitsumon_edit, name="shitsumon_edit"),

    # Sensei (HTML)
    path("sensei/", portal_views.sensei_dashboard, name="sensei_dashboard"),
    path("sensei/<str:public_id>/review/", portal_views.sensei_review, name="sensei_review"),

    path("api/auth/csrf/", auth_views.csrf, name="csrf"),
    path("api/auth/me/", auth_views.me, name="me"),
    path("api/auth/register/", auth_views.register_view, name="register"),
    path("api/auth/login/", auth_views.login_view, name="login"),
    path("api/auth/logout/", auth_views.logout_view, name="logout"),

    path("api/daily-quiz/", views.daily_quiz, name="daily_quiz"),
    path("api/submit-answer/", views.submit_answer, name="submit_answer"),
    path("api/video/<int:weekly_content_id>/", views.protected_video, name="protected_video"),
    path(
        "api/video/<int:weekly_content_id>/completed/",
        views.mark_video_completed,
        name="mark_video_completed",
    ),
    path("api/certificate/", views.generate_certificate, name="generate_certificate"),

    path("api/path/", path_views.learning_path, name="learning_path"),
    path("api/referrals/", referral_views.referral_dashboard, name="referral_dashboard"),
    path("api/reviews/due/", review_views.due_reviews, name="due_reviews"),
    path("api/colleges/", views.colleges_list, name="colleges_list"),
    path("api/mondai/<str:public_id>/", views.mondai_detail, name="mondai_detail"),

    path("api/billing/plans/", billing_views.plans, name="plans"),
    path(
        "api/billing/checkout-session/",
        billing_views.create_checkout_session,
        name="checkout_session",
    ),
]
