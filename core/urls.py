from django.urls import path

from . import auth_views, billing_views, path_views, portal_views, referral_views, review_views, views
from payments import views as payments_views


urlpatterns = [
    # Portal (HTML)
    path("", portal_views.portal_index, name="portal_index"),
    path("portal/login/", portal_views.portal_login, name="portal_login"),
    path("portal/logout/", portal_views.portal_logout, name="portal_logout"),

    # Shitsumon (HTML)
    path("shitsumon/", portal_views.shitsumon_dashboard, name="shitsumon_dashboard"),
    path("shitsumon/new/", portal_views.shitsumon_create, name="shitsumon_create"),
    path("shitsumon/<str:public_id>/edit/", portal_views.shitsumon_edit, name="shitsumon_edit"),
    path("shitsumon/<str:public_id>/fix-week/", portal_views.shitsumon_fix_week, name="shitsumon_fix_week"),
    path("shitsumon/<str:public_id>/transcribe/", portal_views.shitsumon_transcribe, name="shitsumon_transcribe"),

    # Sensei (HTML)
    path("sensei/", portal_views.sensei_dashboard, name="sensei_dashboard"),
    path("sensei/<str:public_id>/review/", portal_views.sensei_review, name="sensei_review"),

    path("api/auth/csrf/", auth_views.csrf, name="csrf"),
    path("api/auth/me/", auth_views.me, name="me"),
    path("api/auth/register/", auth_views.register_view, name="register"),
    path("api/auth/login/", auth_views.login_view, name="login"),
    path("api/auth/logout/", auth_views.logout_view, name="logout"),
    path("api/auth/totp/confirm/", auth_views.totp_confirm, name="totp_confirm"),

    path("api/daily-quiz/", views.daily_quiz, name="daily_quiz"),
    path("api/submit-answer/", views.submit_answer, name="submit_answer"),

    # Real leaderboard + weekly (Mondai) study/quiz
    path("api/leaderboard/", views.leaderboard, name="leaderboard"),
    path("api/week/list/", views.fixed_week_list, name="fixed_week_list"),
    path("api/week/current/", views.current_week_content, name="current_week_content"),
    path("api/week/current/study/", views.week_study_questions, name="week_study_questions"),
    path("api/week/current/quiz/", views.daily_week_quiz, name="daily_week_quiz"),
    path("api/week/current/quiz/retake/", views.daily_week_quiz_retake, name="daily_week_quiz_retake"),
    path("api/daily-task/", views.daily_task, name="daily_task"),
    path("api/submit-mondai-answer/", views.submit_mondai_answer, name="submit_mondai_answer"),

    # Email OTP endpoints
    path("api/send-email-otp/", views.send_email_otp, name="send_email_otp"),
    path("api/verify-email-otp/", views.verify_email_otp, name="verify_email_otp"),

    path("api/quiz/history/", views.quiz_history, name="quiz_history"),
    path("api/quiz/history/<str:date_str>/", views.quiz_history_detail, name="quiz_history_detail"),
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
    path("api/colleges/public/", views.colleges_public, name="colleges_public"),
    path("api/mondai/<str:public_id>/", views.mondai_detail, name="mondai_detail"),

    # Course System APIs
    path("api/course/levels/", views.levels_list, name="levels_list"),
    path("api/course/level/<int:level_id>/units/", views.units_list, name="units_list"),
    path("api/course/unit/<int:unit_id>/vocabulary/study/", views.vocabulary_study, name="vocabulary_study"),
    path("api/course/unit/<int:unit_id>/vocabulary/quiz/", views.vocabulary_quiz, name="vocabulary_quiz"),
    path("api/course/unit/<int:unit_id>/grammar/", views.grammar_view, name="grammar_view"),
    path("api/course/unit/<int:unit_id>/adaptive-quiz/", views.adaptive_quiz_session, name="adaptive_quiz_session"),
    path("api/course/vocab-state/submit/", views.vocab_state_submit, name="vocab_state_submit"),
    path("api/course/unit/<int:unit_id>/mastery/", views.unit_mastery, name="unit_mastery"),
    path("api/auth/growth-theme/", auth_views.update_growth_theme, name="update_growth_theme"),

    path("api/billing/plans/", billing_views.plans, name="plans"),
    path("api/billing/cashfree-order/", billing_views.cashfree_create_order, name="cashfree_create_order"),
    path("api/billing/cashfree-webhook/", billing_views.cashfree_webhook, name="cashfree_webhook"),
    path("api/billing/cashfree-verify/", billing_views.cashfree_verify, name="cashfree_verify"),

    # Master payments feature flag (DB-driven)
    path("api/payments/master/", payments_views.master_payments, name="master_payments"),
    path(
        "api/billing/checkout-session/",
        billing_views.create_checkout_session,
        name="checkout_session",
    ),
]
