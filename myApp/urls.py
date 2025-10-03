from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("contact/submit/", views.contact_submit, name="contact_submit"),
    # single chat endpoint
    path("chatbot-response/", views.chatbot_response, name="chatbot_response"),
    path("about/", views.about, name="about"),  # ✅ add this
]
