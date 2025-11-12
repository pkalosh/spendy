from django.urls import path
from userauths import views

app_name = "userauths"

urlpatterns = [
    path("", views.homeView, name="home"),
    path("contact", views.contact, name="contact"),
    path("request-demo", views.demo, name="demo"),
    path("sign-up/", views.RegisterView, name="sign-up"),
    path("sign-in/", views.LoginView, name="sign-in"),
    path("sign-out/", views.logoutView, name="sign-out"),
    path("reset-password/", views.reset_passwordView, name="reset-password"),
    path("reset-password/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    path("change-password/", views.change_passwordView, name="change-password"),
]