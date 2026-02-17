from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import requests
import logging
import secrets
import json
import time
from .models import CanvasToken, Course, Module, ModuleAnalysis, ChatMessage
from .canvas_auth import (
    get_valid_canvas_token, 
    refresh_canvas_token, 
    make_canvas_request,
    detect_user_role,
    sync_courses_for_user,
    sync_modules_for_course
)
from .debug_service import get_debug_service
from .rag_service import get_rag_service

logger = logging.getLogger(__name__)


def test_api(request):
    """
    Endpoint de prueba para diagnosticar problemas AJAX.
    """
    if request.method == 'POST':
        return JsonResponse({
            'status': 'ok',
            'message': 'API respondiendo correctamente JSON',
            'authenticated': request.user.is_authenticated,
            'username': request.user.username if request.user.is_authenticated else 'Anónimo'
        })
    return JsonResponse({'error': 'Use POST'}, status=400)


def index(request):
    """
    Página principal. Muestra el botón de login o el dashboard según el rol.
    """
    if not request.user.is_authenticated:
        return render(request, 'tu_app/index.html', {'is_authenticated': False})
    
    # Obtenemos el token del usuario
    try:
        canvas_token = request.user.canvas_token
        access_token = get_valid_canvas_token(request.user)
        
        if not access_token:
            return render(request, 'tu_app/error.html', {
                'error': 'Tu sesión de Canvas ha expirado. Por favor, vuelve a conectar.'
            })
        
        # Detectamos el rol si es desconocido
        if canvas_token.role == 'unknown':
            detect_user_role(request.user)
            canvas_token.refresh_from_db()
        
        # Sincronizamos cursos desde Canvas
        courses = sync_courses_for_user(request.user)
        
        # Para estudiantes, también sincronizamos módulos
        if canvas_token.is_student():
            # Sincronizamos módulos de cada curso
            for course in courses:
                sync_modules_for_course(request.user, course)
            
            # Obtenemos los módulos de la BD
            modules = Module.objects.filter(course__user=request.user).select_related('course')
        else:
            modules = []
        
        return render(request, 'tu_app/index.html', {
            'is_authenticated': True,
            'user': request.user,
            'user_role': canvas_token.get_role_display(),
            'is_teacher': canvas_token.is_teacher(),
            'is_student': canvas_token.is_student(),
            'courses': courses,
            'modules': modules,
            'user_id': canvas_token.canvas_user_id
        })
        
    except CanvasToken.DoesNotExist:
        logger.warning(f"User {request.user.username} has no Canvas token")
        return render(request, 'tu_app/error.html', {
            'error': 'No has vinculado tu cuenta de Canvas. Por favor, inicia sesión nuevamente.'
        })
    except Exception as e:
        logger.error(f"Error in index view for user {request.user.username}: {str(e)}")
        return render(request, 'tu_app/error.html', {
            'error': f'Error: {str(e)}'
        })


def canvas_login(request):
    """
    Paso 1 del flujo: Redirige al usuario a la página de autorización de Canvas.
    Genera un state token para seguridad CSRF.
    """
    # Generamos un state token aleatorio para seguridad
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    
    auth_url = (
        f"{settings.CANVAS_BASE_URL}/login/oauth2/auth"
        f"?client_id={settings.CANVAS_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.CANVAS_REDIRECT_URI}"
        f"&state={state}"
        f"&scope=url:GET|/api/v1/courses"
    )
    return redirect(auth_url)


def canvas_callback(request):
    """
    Paso 2 del flujo: Canvas nos redirige aquí con un código.
    Validamos el state, intercambiamos el código por un token y lo guardamos en BD.
    """
    # Validamos el state para seguridad CSRF
    state = request.GET.get('state')
    session_state = request.session.get('oauth_state')
    
    if not state or state != session_state:
        logger.warning(f"State mismatch or missing in OAuth callback")
        return render(request, 'tu_app/error.html', {
            'error': 'Sesión incorrecta o no presentada para OAuth. Por favor, intenta de nuevo.'
        })
    
    # Limpiamos el state de la sesión
    del request.session['oauth_state']
    
    auth_code = request.GET.get('code')
    if not auth_code:
        return render(request, 'tu_app/error.html', {'error': 'No se recibió el código de autorización.'})

    token_url = f"{settings.CANVAS_BASE_URL}/login/oauth2/token"
    payload = {
        'grant_type': 'authorization_code',
        'client_id': settings.CANVAS_CLIENT_ID,
        'client_secret': settings.CANVAS_CLIENT_SECRET,
        'redirect_uri': settings.CANVAS_REDIRECT_URI,
        'code': auth_code,
    }

    headers = {
        'User-Agent': 'KairosProject/1.0 (pruzhk4)'
    }

    try:
        response = requests.post(token_url, data=payload, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Obtenemos o creamos el usuario de Django
        canvas_user_id = token_data['user']['id']
        
        # Generamos un username único basado en los datos disponibles
        login_name = (
            token_data['user'].get('login') or 
            token_data['user'].get('email', '').split('@')[0] or 
            f"canvas_user_{canvas_user_id}"
        )
        
        user, created = User.objects.get_or_create(
            username=login_name,
            defaults={
                'email': token_data['user'].get('email', ''),
                'first_name': token_data['user'].get('name', '').split()[0] if token_data['user'].get('name') else '',
                'last_name': ' '.join(token_data['user'].get('name', '').split()[1:]) if token_data['user'].get('name') else '',
            }
        )
        
        # Calculamos la fecha de expiración
        expires_in = token_data.get('expires_in', 3600)
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        # Guardamos o actualizamos el token en BD
        canvas_token, _ = CanvasToken.objects.update_or_create(
            user=user,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', ''),
                'canvas_user_id': canvas_user_id,
                'expires_at': expires_at,
                'scopes': token_data.get('scope', ''),
                'role': 'unknown',  # Se detectará más tarde
            }
        )
        
        # Autenticamos el usuario en Django
        request.session['_auth_user_id'] = user.id
        request.session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        request.session['_auth_user_hash'] = user.get_session_auth_hash()
        
        # Detectamos el rol automáticamente
        detect_user_role(user)
        
        logger.info(f"User {user.username} authenticated successfully with Canvas token")
        
        return redirect('index')

    except requests.exceptions.RequestException as e:
        response_details = e.response.text if e.response else 'No response from server'
        logger.error(f"Error requesting Canvas token: {str(e)}. Details: {response_details}")
        
        return render(request, 'tu_app/error.html', {
            'error': 'Ocurrió un error durante la autenticación con Canvas. Por favor, inténtalo de nuevo.'
        })


def canvas_logout(request):
    """
    Limpia la sesión del usuario.
    """
    from django.contrib.auth import logout
    logout(request)
    return redirect('index')


def module_detail(request, module_id):
    """
    Detalle de un módulo con opción de analizar para RAG.
    """
    if not request.user.is_authenticated:
        return redirect('canvas_login')
    
    try:
        module = Module.objects.get(id=module_id, course__user=request.user)
        items = module.items.all()
        analysis = module.analysis
        
        return render(request, 'tu_app/module_detail.html', {
            'module': module,
            'items': items,
            'analysis': analysis,
        })
    except Module.DoesNotExist:
        return render(request, 'tu_app/error.html', {
            'error': 'Módulo no encontrado.'
        })


@require_http_methods(["POST"])
def analyze_module_api(request, module_id):
    """
    API endpoint para iniciar análisis de un módulo.
    """
    # Verificar autenticación
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado - por favor inicia sesión primero'}, status=401)
    
    from .rag_service import get_rag_service
    
    try:
        module = Module.objects.get(id=module_id, course__user=request.user)
        
        # Obtenemos el analysis o lo creamos
        analysis, created = ModuleAnalysis.objects.get_or_create(module=module)
        
        # Actualizamos status a 'analyzing'
        analysis.status = 'analyzing'
        analysis.save()
        
        # Obtenemos token válido
        access_token = get_valid_canvas_token(request.user)
        if not access_token:
            analysis.status = 'failed'
            analysis.error_message = 'Token de Canvas expirado'
            analysis.save()
            return JsonResponse({'error': 'Token de Canvas expirado'}, status=401)
        
        try:
            # Ejecutamos RAG analysis (puede ser lento)
            logger.info(f"Starting RAG analysis for module {module.id}")
            rag_service = get_rag_service()
            rag_service.analyze_module(module, access_token)
            
            # Actualizamos status
            analysis.status = 'completed'
            analysis.total_items_processed = module.items.count()
            analysis.vector_db_path = f"module_{module.id}_course_{module.course.id}"
            analysis.save()
            
            logger.info(f"Module {module.id} analysis completed for user {request.user.username}")
            return JsonResponse({
                'status': 'completed',
                'message': f'Módulo {module.name} analizado correctamente.',
                'items_processed': module.items.count()
            })
            
        except Exception as e:
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.save()
            logger.error(f"Error analyzing module {module.id}: {str(e)}", exc_info=True)
            return JsonResponse({'error': f'Error al analizar: {str(e)}'}, status=500)
    
    except Module.DoesNotExist:
        return JsonResponse({'error': 'Módulo no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Unexpected error in analyze_module_api: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)


@login_required
def chat_view(request, course_id):
    """
    Vista de chat para estudiantes hacer preguntas sobre el curso.
    """
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        modules = course.modules.prefetch_related('items', 'analysis')
        
        # Obtenemos últimos 50 mensajes del chat
        chat_history = ChatMessage.objects.filter(
            user=request.user,
            course=course
        ).order_by('-created_at')[:50]
        
        return render(request, 'tu_app/chat.html', {
            'course': course,
            'modules': modules,
            'chat_history': reversed(chat_history),
        })
    except Course.DoesNotExist:
        return render(request, 'tu_app/error.html', {
            'error': 'Curso no encontrado.'
        })


@require_http_methods(["POST"])
def chat_api(request):
    """
    API endpoint para manejar preguntas y respuestas de IA.
    POST: Envía una pregunta y recibe respuesta de DeepSeek con contexto RAG.
    """
    # Verificar autenticación
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    
    from .rag_service import get_rag_service
    from .ai_service import get_ai_service
    
    try:
        data = json.loads(request.body)
        
        question = data.get('question', '').strip()
        course_id = data.get('course_id')
        module_id = data.get('module_id')
        
        if not question:
            return JsonResponse({'error': 'Pregunta vacía'}, status=400)
        
        
        # Verificamos que el usuario tenga acceso al curso
        course = Course.objects.get(id=course_id, user=request.user)
        module = Module.objects.get(id=module_id, course=course) if module_id else None
        
        # Guardamos la pregunta del estudiante
        student_message = ChatMessage.objects.create(
            user=request.user,
            course=course,
            module=module,
            role='student',
            content=question
        )
        
        try:
            # Obtenemos contexto con RAG
            rag_service = get_rag_service()
            
            # Si no hay módulo específico, buscamos en todos
            if module:
                context = rag_service.search_context(question, module.id, course.id)
            else:
                # Buscar en todos los módulos del curso
                context = []
                for mod in course.modules.all():
                    mod_context = rag_service.search_context(question, mod.id, course.id)
                    context.extend(mod_context)
            
            # Obtenemos respuesta de DeepSeek
            ai_service = get_ai_service()
            start_time = time.time()
            
            ai_response = ai_service.answer_question(
                question=question,
                context=context,
                user=request.user
            )
            
            processing_time = time.time() - start_time
            tokens = ai_response.get('tokens_used', 0)
            answer = ai_response.get('answer', '')
            
            # Guardamos la respuesta de IA
            ai_message = ChatMessage.objects.create(
                user=request.user,
                course=course,
                module=module,
                role='ai',
                content=answer,
                tokens_used=tokens,
                processing_time=processing_time,
                model_used='deepseek'
            )
            
            logger.info(f"Chat processed for user {request.user.username} - {tokens} tokens, {processing_time:.2f}s")
            
            return JsonResponse({
                'success': True,
                'response': answer,
                'tokens_used': tokens,
                'processing_time': f'{processing_time:.2f}',
                'message_id': ai_message.id
            })
        except Exception as e:
            logger.error(f"Error processing AI response for user {request.user.username}: {str(e)}")
            return JsonResponse({'error': f'Error en procesamiento de IA: {str(e)}'}, status=500)
        
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Curso no encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error in chat_api for user {request.user.username}: {str(e)}")
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)


# ============================================================================
# ENDPOINTS DE DEBUGGING - Para ver qué está pasando adentro del sistema
# ============================================================================

@require_http_methods(["GET"])
def debug_events(request):
    """
    Endpoint para obtener los eventos recientes del sistema.
    Útil para debugging en desarrollo.
    
    Parámetros:
    - type: Filtrar por tipo de evento (RAG, DEEPSEEK, EMBEDDING, ERROR)
    - limit: Número de eventos a retornar (default: 50)
    """
    try:
        event_type = request.GET.get('type', None)
        limit = int(request.GET.get('limit', 50))
        
        debug_service = get_debug_service()
        events = debug_service.get_recent_events(event_type=event_type, limit=limit)
        
        return JsonResponse({
            'status': 'ok',
            'events': events,
            'total_events': len(debug_service.events),
            'event_type_filter': event_type,
        })
    except Exception as e:
        logger.error(f"Error in debug_events: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def debug_stats(request):
    """
    Endpoint para obtener estadísticas del sistema.
    Incluye stats de RAG, DeepSeek, memoria, etc.
    """
    try:
        debug_service = get_debug_service()
        stats = debug_service.get_stats()
        
        return JsonResponse({
            'status': 'ok',
            'timestamp': stats['timestamp'],
            'rag': stats['rag'],
            'deepseek': stats['deepseek'],
            'memory_db': stats['memory_db'],
            'event_counts': stats['event_types'],
        })
    except Exception as e:
        logger.error(f"Error in debug_stats: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def debug_documents(request):
    """
    Endpoint para obtener los documentos que fueron analizados.
    
    Parámetros:
    - module_id: Filtrar por ID de módulo (opcional)
    """
    try:
        module_id = request.GET.get('module_id', None)
        debug_service = get_debug_service()
        
        if module_id:
            documents = debug_service.get_analyzed_documents(int(module_id))
        else:
            documents = debug_service.get_analyzed_documents()
        
        return JsonResponse({
            'status': 'ok',
            'documents': documents,
        })
    except Exception as e:
        logger.error(f"Error in debug_documents: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def check_module_analysis_status(request, module_id):
    """
    Endpoint para verificar si un módulo tiene embeddings guardados.
    Retorna el estado real de los datos para sincronización de UI.
    
    Respuesta:
    {
        'is_analyzed': True/False,
        'document_count': N,
        'embedding_count': N,
        'db_source': 'chromadb' o 'memory',
        'last_updated': timestamp
    }
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    
    try:
        module = Module.objects.get(id=module_id, course__user=request.user)
        rag_service = get_rag_service()
        debug_service = get_debug_service()
        
        # Obtenemos documentos del debug service
        analyzed_docs = debug_service.get_analyzed_documents(module_id)
        document_count = len(analyzed_docs.get('documents', []))
        
        # Verificamos si hay embeddings en la RAG service
        collection_name = f"module_{module.id}_course_{module.course.id}"
        has_embeddings = rag_service.check_collection_exists(collection_name)
        
        # Si el debug service registró documentos, usamos eso
        # Si no, verificamos la BD
        try:
            analysis = ModuleAnalysis.objects.get(module=module)
            db_status = analysis.status
        except ModuleAnalysis.DoesNotExist:
            analysis = None
            db_status = 'not_analyzed'
        
        is_analyzed = document_count > 0 or has_embeddings
        
        return JsonResponse({
            'status': 'ok',
            'module_id': module_id,
            'is_analyzed': is_analyzed,
            'document_count': document_count,
            'db_status': db_status,
            'has_embeddings': has_embeddings,
            'collection_name': collection_name
        })
    
    except Module.DoesNotExist:
        return JsonResponse({'error': 'Módulo no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error checking analysis status: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def debug_dashboard(request):
    """
    Dashboard visual para ver qué está pasando en el sistema.
    Muestra eventos en tiempo real, estadísticas, etc.
    """
    return render(request, 'tu_app/debug_dashboard.html')

