from django.urls import path
from . import views

urlpatterns = [
    path("requests/send/", views.send_friend_request, name="send_friend_request"),
    path("requests/incoming/", views.incoming_requests, name="incoming_requests"),
    path("requests/respond/", views.respond_to_request, name="respond_to_request"),
    path("friends/", views.friends_list, name="friends_list"),
    path("search/", views.search_users, name="search_users"),
    path("profile/", views.get_or_update_profile, name="social_profile"),
    path("profile/<int:user_id>/", views.public_profile, name="public_profile"),
    path("conversations/", views.conversations_list, name="conversations_list"),
    path("chat/<int:partner_id>/", views.chat_messages, name="chat_messages"),
    path("mutual-streaks/", views.mutual_streaks, name="mutual_streaks"),
]
