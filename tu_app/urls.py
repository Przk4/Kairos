# tu_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.canvas_login, name='canvas_login'),
    # ¡Asegúrate de que esta ruta coincida con la nueva URI!
    path('callback/', views.canvas_callback, name='canvas_callback'), 
    path('logout/', views.canvas_logout, name='canvas_logout'),
    
    # Rutas para módulos y chat
    path('module/<int:module_id>/', views.module_detail, name='module_detail'),
    path('api/analyze-module/<int:module_id>/', views.analyze_module_api, name='analyze_module_api'),
    path('course/<int:course_id>/chat/', views.chat_view, name='chat'),
    path('api/chat/', views.chat_api, name='chat_api'),
    
    # Endpoint de diagnóstico
    path('api/test/', views.test_api, name='test_api'),
    path('api/debug/events/', views.debug_events, name='debug_events'),
    path('api/debug/stats/', views.debug_stats, name='debug_stats'),
    path('api/debug/documents/', views.debug_documents, name='debug_documents'),
    path('api/debug/rag-status/', views.debug_rag_status, name='debug_rag_status'),
    path('api/debug/prompt-flow/', views.debug_prompt_flow, name='debug_prompt_flow'),
    path('api/module/<int:module_id>/analysis-status/', views.check_module_analysis_status, name='check_analysis_status'),
    path('api/test-button-click/', views.test_button_click, name='test_button_click'),
    path('test-button/', views.test_button_page, name='test_button'),
    path('debug/dashboard/', views.debug_dashboard, name='debug_dashboard'),
]