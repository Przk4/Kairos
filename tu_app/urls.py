# tu_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.canvas_login, name='canvas_login'),
    # ¡Asegúrate de que esta ruta coincida con la nueva URI!
    path('callback/', views.canvas_callback, name='canvas_callback'), 
    path('logout/', views.canvas_logout, name='canvas_logout'),
]
