# tu_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.canvas_login, name='canvas_login'),
    path('callback/', views.canvas_callback, name='canvas_callback'), 
    path('logout/', views.canvas_logout, name='canvas_logout'),
    
    # Routes for modules and chat
    path('module/<int:module_id>/', views.module_detail, name='module_detail'),
    path('api/analyze-module/<int:module_id>/', views.analyze_module_api, name='analyze_module_api'),
    path('course/<int:course_id>/chat/', views.chat_view, name='chat'),
    path('api/chat/', views.chat_api, name='chat_api'),
    
    # Teacher routes
    path('teacher/course/<int:course_id>/', views.teacher_course_detail, name='teacher_course_detail'),
    path('api/teacher/course/<int:course_id>/students/', views.api_teacher_course_students, name='api_teacher_course_students'),
    path('api/teacher/course/<int:course_id>/ai-generate/', views.api_teacher_ai_generate, name='api_teacher_ai_generate'),
    path('api/teacher/course/<int:course_id>/create-assignment/', views.api_teacher_create_assignment, name='api_teacher_create_assignment'),
    path('api/teacher/course/<int:course_id>/assignment-groups/', views.api_teacher_assignment_groups, name='api_teacher_assignment_groups'),
    
    # NEW: Module stats endpoint for dashboard
    path('api/modules/stats-all/', views.get_all_modules_stats, name='get_all_modules_stats'),
    
    # Extension endpoints
    path('api/extension/ask/', views.extension_ask, name='extension_ask'),
    path('api/extension/auth/', views.extension_check_auth, name='extension_check_auth'),
    path('api/extension/courses/', views.extension_courses, name='extension_courses'),
    
    # Module analysis status
    path('api/module/<int:module_id>/analysis-status/', views.check_module_analysis_status, name='check_analysis_status'),
    
    # Debug dashboard
    path('debug/dashboard/', views.debug_dashboard, name='debug_dashboard'),
    path('api/debug/prompt-flow/', views.debug_api_prompt_flow, name='debug_prompt_flow'),
    path('api/debug/logs/', views.debug_api_logs, name='debug_logs'),
]
