from django.urls import path, include
from . import views

# urls.py
urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('signup', views.signup_view, name='signup'),
    path('signin', views.login_view, name='signin'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('generate', views.generate_chart, name='generate_chart'),
]
