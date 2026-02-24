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
    
    # Debug endpoints
    path('api/test/', views.test_api, name='test_api'),
    path('api/debug/events/', views.debug_events, name='debug_events'),
    path('api/debug/stats/', views.debug_stats, name='debug_stats'),
    path('api/debug/documents/', views.debug_documents, name='debug_documents'),
    path('api/debug/rag-status/', views.debug_rag_status, name='debug_rag_status'),
    path('api/debug/prompt-flow/', views.debug_prompt_flow, name='debug_prompt_flow'),
    path('api/debug/question-embeddings/', views.debug_question_embeddings, name='debug_question_embeddings'),
    path('api/debug/test-data/', views.debug_test_data, name='debug_test_data'),
    path('api/module/<int:module_id>/analysis-status/', views.check_module_analysis_status, name='check_analysis_status'),
    path('api/test-button-click/', views.test_button_click, name='test_button_click'),
    path('test-button/', views.test_button_page, name='test_button'),
    path('debug/dashboard/', views.debug_dashboard, name='debug_dashboard'),
]
