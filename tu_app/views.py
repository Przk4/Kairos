from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from datetime import timedelta
import requests
import logging
import secrets
import json
import time
from urllib.parse import urlencode, urlparse
from .models import CanvasToken, Course, Module, ModuleAnalysis, ModuleEmbedding, ChatMessage, StudentProfile, LoginRecord
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
from .ai_service import get_ai_service
from .query_analyzer import get_query_analyzer

logger = logging.getLogger(__name__)


def _get_canvas_redirect_uri(request):
    """
    Obtiene una redirect_uri válida y consistente para OAuth.
    - Usa CANVAS_REDIRECT_URI si está configurada.
    - Si la config apunta a localhost pero la petición llega por otro host,
      usa la URL absoluta del callback actual para evitar redirecciones inválidas.
    """
    configured_uri = (getattr(settings, 'CANVAS_REDIRECT_URI', '') or '').strip()
    request_callback_uri = request.build_absolute_uri(reverse('canvas_callback'))

    if not configured_uri:
        return request_callback_uri

    try:
        configured_host = (urlparse(configured_uri).hostname or '').lower()
    except Exception:
        configured_host = ''

    request_host = request.get_host().split(':')[0].lower()
    if configured_host in {'127.0.0.1', 'localhost'} and request_host not in {'127.0.0.1', 'localhost'}:
        logger.warning(
            "CANVAS_REDIRECT_URI apunta a localhost pero la petición llegó por %s. "
            "Usando callback dinámico: %s",
            request_host,
            request_callback_uri,
        )
        return request_callback_uri

    return configured_uri

# Almacenamiento temporal del último flujo de prompt para debug
# NOTA: Solo para desarrollo. En producción con múltiples workers,
# usar Django cache framework (Redis/Memcached) en su lugar.
_last_prompt_flow = {
    'question': None,
    'question_length': 0,
    'retrieved_count': 0,
    'retrieved_docs': [],
    'context': None,
    'system_prompt': None,
    'full_user_prompt': None,
    'response': None,
    'timestamp': None
}


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
    
    redirect_uri = _get_canvas_redirect_uri(request)
    auth_params = {
        'client_id': settings.CANVAS_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': 'url:GET|/api/v1/courses',
    }
    auth_url = f"{settings.CANVAS_BASE_URL}/login/oauth2/auth?{urlencode(auth_params)}"
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
    redirect_uri = _get_canvas_redirect_uri(request)
    payload = {
        'grant_type': 'authorization_code',
        'client_id': settings.CANVAS_CLIENT_ID,
        'client_secret': settings.CANVAS_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
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
        # No resetear role si ya fue detectado previamente
        existing_role = 'unknown'
        try:
            existing_token = CanvasToken.objects.get(user=user)
            existing_role = existing_token.role if existing_token.role != 'unknown' else 'unknown'
        except CanvasToken.DoesNotExist:
            pass
        
        canvas_token, _ = CanvasToken.objects.update_or_create(
            user=user,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', ''),
                'canvas_user_id': canvas_user_id,
                'expires_at': expires_at,
                'scopes': token_data.get('scope', ''),
                'role': existing_role,  # Preservar rol si ya fue detectado
            }
        )
        
        # Autenticamos el usuario en Django (usando la función oficial)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        auth_login(request, user)
        
        # Detectamos el rol (siempre re-detectar para mantener actualizado)
        detected_role = detect_user_role(user)
        
        # TRACKING: Si es estudiante, crear/actualizar StudentProfile y registrar login
        if detected_role == 'student':
            profile, profile_created = StudentProfile.objects.get_or_create(
                canvas_user_id=canvas_user_id,
                defaults={
                    'user': user,
                    'display_name': token_data['user'].get('name', user.username),
                    'email': token_data['user'].get('email', ''),
                }
            )
            if not profile_created:
                # Actualizar datos en cada login
                profile.total_logins += 1
                profile.last_login_at = timezone.now()
                profile.display_name = token_data['user'].get('name', profile.display_name)
                profile.save()
            
            # Registrar evento de login individual
            LoginRecord.objects.create(
                student_profile=profile,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            )
            logger.info(f"StudentProfile {'created' if profile_created else 'updated'} for {user.username} (login #{profile.total_logins})")
        
        logger.info(f"User {user.username} authenticated successfully with Canvas token (role: {detected_role})")
        
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
    auth_logout(request)
    return redirect('index')


@login_required
def module_detail(request, module_id):
    """
    Detalle de un módulo con opción de analizar para RAG.
    """
    try:
        module = Module.objects.get(id=module_id, course__user=request.user)
        items = module.items.all()
        try:
            analysis = module.analysis
        except ModuleAnalysis.DoesNotExist:
            analysis = None
        
        return render(request, 'tu_app/module_detail.html', {
            'module': module,
            'items': items,
            'analysis': analysis,
        })
    except Module.DoesNotExist:
        return render(request, 'tu_app/error.html', {
            'error': 'Módulo no encontrado.'
        })


@login_required
@require_http_methods(["POST"])
def analyze_module_api(request, module_id):
    """
    API endpoint para iniciar análisis de un módulo.
    Primero sincroniza items si es necesario, luego analiza.
    """
    from .canvas_auth import sync_module_items
    
    logger.info(f"Analyze request for module {module_id} from user {request.user.username}")
    
    try:
        module = Module.objects.get(id=module_id, course__user=request.user)
        logger.info(f"Module found: {module.name}")
        
        # Obtenemos el analysis o lo creamos
        analysis, created = ModuleAnalysis.objects.get_or_create(module=module)
        
        # Actualizamos status a 'analyzing'
        analysis.status = 'analyzing'
        analysis.save()
        
        # Obtenemos token válido
        logger.info(f"Attempting to get Canvas token for user {request.user.username}")
        access_token = get_valid_canvas_token(request.user)
        if not access_token:
            analysis.status = 'failed'
            analysis.error_message = 'Token de Canvas expirado'
            analysis.save()
            logger.error(f"Canvas token expired for user {request.user.username}")
            return JsonResponse({
                'status': 'failed',
                'error': 'Token de Canvas expirado o no disponible. Por favor, reconéctate con Canvas.'
            }, status=401)
        
        try:
            # PRIMERO: Re-sincronizar items para asegurar URLs correctas
            logger.info(f"Re-syncing items for module {module.id} to ensure correct download URLs")
            headers = {'Authorization': f'Bearer {access_token}'}
            try:
                sync_module_items(request.user, module, headers)
                logger.info(f"Module items synced successfully")
            except Exception as sync_error:
                logger.warning(f"Error syncing module items: {sync_error}")
                # No fallar, continuar con lo que tenemos
            
            # SEGUNDO: Ejecutamos RAG analysis (puede ser lento)
            logger.info(f"Starting RAG analysis for module {module.id}")
            rag_service = get_rag_service()
            
            # LOG: Revisar estado antes del análisis
            logger.info(f"RAG Service status: using_chromadb={rag_service.using_chromadb}, client={bool(rag_service.client)}")
            
            success = rag_service.analyze_module(module, access_token)
            
            if success:
                # VERIFICACIÓN: Contar embeddings después del análisis
                collection_name = f"module_{module.id}_course_{module.course.id}"
                embeddings_count = rag_service.get_embeddings_count(collection_name)
                
                logger.info(f"Module {module.id} analysis result: success={success}, embeddings_count={embeddings_count}")
                
                if embeddings_count == 0:
                    logger.warning(f"⚠️ WARNING: Module {module.id} marked as analyzed but 0 embeddings found! Backend: {rag_service.using_chromadb}")
                    analysis.status = 'failed'
                    analysis.error_message = f'Análisis completado pero sin vectores guardados. Backend: {rag_service.using_chromadb}'
                    analysis.save()
                    return JsonResponse({
                        'status': 'failed',
                        'error': f'Error al guardar vectores. Los embeddings no se guardaron. Backend: {rag_service.using_chromadb}'
                    })
                
                # Actualizamos status
                analysis.status = 'completed'
                analysis.total_items_processed = module.items.count()
                analysis.vector_db_path = f"module_{module.id}_course_{module.course.id}"
                analysis.save()
                
                # GUARDAR EMBEDDINGS EN BD (ModuleEmbedding)
                # El dashboard y chat.html leen de aquí
                try:
                    collection_name_db = f"module_{module.id}_course_{module.course.id}"
                    # Obtener datos del in_memory_db o JSON
                    embedding_data = {}
                    if collection_name_db in rag_service.in_memory_db:
                        embedding_data = rag_service.in_memory_db[collection_name_db]
                    else:
                        # Intentar leer del JSON guardado
                        import os
                        json_path = os.path.join(rag_service.json_embeddings_dir, f"{collection_name_db}.json")
                        if os.path.exists(json_path):
                            import json as json_lib
                            with open(json_path, 'r', encoding='utf-8') as f:
                                embedding_data = json_lib.load(f)
                    
                    doc_count = len(embedding_data.get('documents', []))
                    module_embedding, created = ModuleEmbedding.objects.update_or_create(
                        module=module,
                        defaults={
                            'embedding_data': embedding_data,
                            'document_count': doc_count,
                            'model_name': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
                        }
                    )
                    logger.info(f"✅ ModuleEmbedding saved for module {module.id}: {doc_count} documents ({'created' if created else 'updated'})")
                except Exception as save_err:
                    logger.error(f"⚠️ Error saving ModuleEmbedding for module {module.id}: {save_err}")
                
                logger.info(f"Module {module.id} analysis completed with {embeddings_count} embeddings for user {request.user.username}")
                return JsonResponse({
                    'status': 'completed',
                    'message': f'Módulo "{module.name}" analizado correctamente. {module.items.count()} items, {embeddings_count} vectores guardados.',
                    'items_processed': module.items.count(),
                    'embeddings_count': embeddings_count
                })
            else:
                analysis.status = 'failed'
                analysis.error_message = 'Error durante análisis'
                analysis.save()
                logger.error(f"RAG analysis failed for module {module.id}")
                return JsonResponse({
                    'status': 'failed',
                    'error': 'Error al analizar el módulo. Intenta de nuevo.'
                })
            
        except Exception as e:
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.save()
            logger.error(f"Error analyzing module {module.id}: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'failed',
                'error': f'Error al analizar: {str(e)}'
            }, status=500)
    
    except Module.DoesNotExist:
        logger.warning(f"Module {module_id} not found for user {request.user.username}")
        return JsonResponse({'status': 'failed', 'error': 'Módulo no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Unexpected error in analyze_module_api: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'failed', 'error': f'Error inesperado: {str(e)}'}, status=500)


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


@login_required
@require_http_methods(["POST"])
def chat_api(request):
    """
    API endpoint para manejar preguntas y respuestas de IA.
    POST: Envía una pregunta y recibe respuesta de DeepSeek con contexto RAG.
    Supports JSON body or multipart/form-data (for image uploads).
    """
    try:
        # Parse request — support both JSON and multipart
        image_bytes = None
        image_ocr_text = None
        content_type = request.content_type or ''

        if 'multipart/form-data' in content_type:
            question = request.POST.get('question', '').strip()
            course_id = request.POST.get('course_id')
            module_id = request.POST.get('module_id')
            # Handle uploaded image
            image_file = request.FILES.get('image')
            if image_file:
                image_bytes = image_file.read()
        else:
            data = json.loads(request.body)
            question = data.get('question', '').strip()
            course_id = data.get('course_id')
            module_id = data.get('module_id')
            # Handle base64 image (from extension)
            b64_image = data.get('image_base64', '')
            if b64_image:
                import base64 as _b64
                if ',' in b64_image and b64_image.startswith('data:'):
                    b64_image = b64_image.split(',', 1)[1]
                image_bytes = _b64.b64decode(b64_image)

        # OCR the image if present
        ocr_error = None
        if image_bytes:
            try:
                from .ocr_service import get_ocr_service
                ocr = get_ocr_service()
                image_ocr_text = ocr.extract_text(image_bytes)
                logger.info(f"[CHAT] Image OCR: {len(image_ocr_text)} chars extracted")
            except Exception as e:
                ocr_error = str(e)
                logger.error(f"[CHAT] Image OCR failed: {e}", exc_info=True)

        # Combine question with OCR text
        if image_ocr_text:
            if question:
                question = f"{question}\n\n[Contenido de la imagen adjunta]:\n{image_ocr_text}"
            else:
                question = f"Analiza la siguiente imagen:\n\n{image_ocr_text}"
        elif image_bytes and not question:
            # Image was sent but OCR returned nothing
            detail = f" Error OCR: {ocr_error}" if ocr_error else ""
            question = f"El usuario envió una imagen pero no se pudo extraer texto.{detail}"
            logger.error(f"[CHAT] Image sent but OCR empty.{detail}")

        if not question:
            return JsonResponse({'error': 'Pregunta vacía'}, status=400)
        
        # Verificamos que el usuario tenga acceso al curso
        course = Course.objects.get(id=course_id, user=request.user)
        module = Module.objects.get(id=module_id, course=course) if module_id else None
        
        # Normalizar y guardar la pregunta del estudiante
        try:
            from textwrap import dedent
            import re

            cleaned_question = question if question is not None else ''
            # Normalize line endings
            cleaned_question = cleaned_question.replace('\r\n', '\n').replace('\r', '\n')
            # Remove non-breaking spaces and tabs
            cleaned_question = cleaned_question.replace('\u00A0', ' ').replace('\t', ' ')
            # Remove common indentation and trim
            cleaned_question = dedent(cleaned_question).strip()
            # Collapse excessive blank lines
            cleaned_question = re.sub(r'\n{3,}', '\n\n', cleaned_question)
        except Exception:
            cleaned_question = question

        student_message = ChatMessage.objects.create(
            user=request.user,
            course=course,
            module=module,
            role='student',
            content=cleaned_question
        )
        
        try:
            # Obtenemos contexto con RAG
            rag_service = get_rag_service()
            
            # NUEVO: Analizar pregunta para optimizar búsqueda
            query_analyzer = get_query_analyzer(rag_service.embedding_model)
            query_analysis = query_analyzer.analyze(question)
            
            # Usar número de fragmentos dinámico basado en análisis
            optimal_fragments = query_analysis['num_fragments']
            query_type = query_analysis['query_type']
            
            # Si no hay módulo específico, buscamos en todos
            if module:
                context = rag_service.search_context(
                    question, module.id, course.id, 
                    top_k=optimal_fragments,
                    query_type=query_type  # NUEVO: Para ranking jerárquico
                )
                logger.info(f"[CHAT] Searched module {module.id}: requested={optimal_fragments}, got={len(context)}")
            else:
                # Buscar en todos los módulos del curso
                # Pedir más resultados por módulo, luego re-rankear globalmente
                context = []
                for mod in course.modules.all():
                    mod_context = rag_service.search_context(
                        question, mod.id, course.id, 
                        top_k=optimal_fragments,
                        query_type=query_type
                    )
                    context.extend(mod_context)
                # Re-rank global: ordenar TODOS los resultados y quedarse con los mejores
                context.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
                context = context[:optimal_fragments]
                logger.info(f"[CHAT] Searched {course.modules.count()} modules: global re-rank top {optimal_fragments} from {len(context)} candidates")
            
            # Extraer información de embeddings para debug
            embeddings_info = []
            context_text = ""
            context_count = 0
            
            if context:
                if isinstance(context, list) and len(context) > 0:
                    context_count = len(context)
                    if isinstance(context[0], dict):
                        for i, item in enumerate(context):
                            similarity = item.get('relevance_score', item.get('similarity', 0))
                            item_title = item.get('metadata', {}).get('item_title', 'Unknown')
                            raw_content = item.get('content', '')
                            
                            # Limpiar contenido: remover marcadores de slide y ruido residual
                            import re as _re
                            clean_content = _re.sub(r'\n*---\s*Slide\s*\d+\s*---\n*', '\n', raw_content)
                            clean_content = _re.sub(r'\n*---\s*Página\s*\d+\s*---\n*', '\n', clean_content)
                            # Limpiar cada línea de ruido PPTX
                            clean_lines = []
                            for _line in clean_content.split('\n'):
                                _line = _line.strip()
                                if not _line or len(_line) < 3:
                                    continue
                                if _re.match(r'^\d{1,3}$', _line):
                                    continue
                                if _re.match(r'^20[\dXx]{2}$', _line):
                                    continue
                                if _re.search(r'pie de p[aá]gina|ejemplo de texto|footer|placeholder|click to edit|haga clic', _line, _re.IGNORECASE):
                                    continue
                                if _re.match(r'^(?:©|\(c\)|copyright)\s*20', _line, _re.IGNORECASE):
                                    continue
                                clean_lines.append(_line)
                            clean_content = '\n'.join(clean_lines).strip()
                            
                            # Descartar chunks que quedaron vacíos después de limpiar
                            if not clean_content or len(clean_content) < 15:
                                context_count -= 1
                                continue
                            
                            embeddings_info.append({
                                'rank': i + 1,
                                'title': item_title,
                                'similarity': float(similarity) if similarity else 0.0,
                                'preview': clean_content[:150],
                            })
                            context_text += f"\n[Docs {i+1}] {item_title}\n{clean_content}"
                    else:
                        context_text = str(context)
            
            # GUARDAR FLUJO PARA DEBUG
            global _last_prompt_flow
            
            # Obtener system prompt para mostrarlo en dashboard
            from tu_app.ai_service_config import DeepSeekProvider
            system_prompt = DeepSeekProvider.SYSTEM_PROMPT
            
            # Construir el prompt completo tal cual se envía a DeepSeek
            full_user_prompt = f"""Contexto del curso:\n{context_text}\n\nPregunta del estudiante:\n{question}\n\nPor favor, responde basándote en el contexto proporcionado."""
            
            _last_prompt_flow = {
                'question': question,
                'question_length': len(question),
                'query_analysis': query_analysis,  # NUEVO: Análisis inteligente de pregunta
                'requested_chunks': optimal_fragments,  # NUEVO: Cuántos se solicitaron
                'retrieved_count': context_count,  # Cuántos se recibieron
                'retrieved_docs': embeddings_info,
                'context': context_text,  # SIN TRUNCAR - completo
                'system_prompt': system_prompt,
                'full_user_prompt': full_user_prompt,
                'response': None,  # Se actualiza después
                'timestamp': timezone.now().isoformat()
            }
            
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

            # Clean and normalize AI answer formatting:
            # - Remove common indentation (dedent)
            # - Trim leading/trailing whitespace
            # - Strip trailing spaces on each line
            # - Collapse excessive blank lines (3+ -> 2)
            try:
                import re
                from textwrap import dedent

                if answer and isinstance(answer, str):
                    cleaned = dedent(answer)
                    cleaned = cleaned.strip()
                    # Remove trailing spaces per line
                    cleaned = '\n'.join([ln.rstrip() for ln in cleaned.splitlines()])
                    # Collapse multiple blank lines to at most two
                    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
                    answer = cleaned
            except Exception as _e:
                logger.warning(f"Answer cleaning failed: {_e}")
            
            # ACTUALIZAR RESPUESTA EN FLUJO DEBUG
            _last_prompt_flow['response'] = answer
            
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
# VISTAS DE PROFESORES — Panel de cursos y lista de alumnos
# ============================================================================

@login_required
def teacher_course_detail(request, course_id):
    """
    Vista detallada de un curso para el profesor.
    Muestra la lista de alumnos inscritos en Canvas, marcando en verde
    los que ya iniciaron sesión en Kairos.
    
    Flujo:
    1. Verificar que el usuario es profesor
    2. Obtener lista de enrollments del curso via Canvas API
    3. Cruzar canvas_user_id con StudentProfile de Kairos
    4. Renderizar template con data combinada
    """
    try:
        canvas_token = request.user.canvas_token
        
        if not canvas_token.is_teacher():
            return render(request, 'tu_app/error.html', {
                'error': 'Acceso restringido a profesores.'
            })
        
        # Obtener el curso del profesor
        course = Course.objects.get(id=course_id, user=request.user)
        
        return render(request, 'tu_app/teacher_course_detail.html', {
            'course': course,
            'user': request.user,
        })
        
    except CanvasToken.DoesNotExist:
        return render(request, 'tu_app/error.html', {
            'error': 'No se encontró token de Canvas.'
        })
    except Course.DoesNotExist:
        return render(request, 'tu_app/error.html', {
            'error': 'Curso no encontrado.'
        })


@login_required
@require_http_methods(["GET"])
def api_teacher_course_students(request, course_id):
    """
    API endpoint: Obtiene la lista de estudiantes de un curso.
    
    Arquitectura:
    - Fuente primaria: Canvas API /courses/{id}/enrollments (source of truth)
    - Enriquecimiento: Cruza con StudentProfile de Kairos para estado de login
    
    Esto es correcto para producción porque:
    - Canvas es la fuente de verdad para inscripciones (no duplicamos datos)
    - Kairos solo trackea SU propia data (logins, actividad)
    - Si Canvas cambia inscripciones, se refleja automáticamente
    
    Respuesta:
    {
        'students': [
            {
                'canvas_user_id': 12345,
                'name': 'Juan Pérez',
                'email': 'juan@example.com',
                'has_kairos_session': True,    # ¿Ha iniciado sesión en Kairos?
                'total_logins': 15,            # Total de logins en Kairos
                'logins_this_week': 3,         # Logins esta semana
                'first_login': '2026-01-15',   # Primer login
                'last_login': '2026-02-23',    # Último login
            },
            ...
        ],
        'total_students': 30,
        'students_in_kairos': 18
    }
    """
    try:
        canvas_token = request.user.canvas_token
        
        if not canvas_token.is_teacher():
            return JsonResponse({'error': 'Acceso restringido a profesores'}, status=403)
        
        course = Course.objects.get(id=course_id, user=request.user)
        
        # Obtener token válido de Canvas
        from .canvas_auth import get_valid_canvas_token
        access_token = get_valid_canvas_token(request.user)
        if not access_token:
            return JsonResponse({'error': 'Token de Canvas expirado'}, status=401)
        
        # Consultar Canvas API para obtener inscripciones de estudiantes
        headers = {'Authorization': f'Bearer {access_token}'}
        enrollments_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses/{course.canvas_course_id}/enrollments"
        
        all_enrollments = []
        page = 1
        
        # Paginación de Canvas API (puede haber muchos estudiantes)
        while True:
            response = requests.get(
                enrollments_url,
                headers=headers,
                params={
                    'type[]': 'StudentEnrollment',
                    'state[]': 'active',
                    'per_page': 100,
                    'page': page,
                }
            )
            response.raise_for_status()
            
            page_data = response.json()
            if not page_data:
                break
            
            all_enrollments.extend(page_data)
            
            # Revisar si hay más páginas (Canvas usa Link header)
            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header:
                break
            page += 1
        
        # Obtener todos los StudentProfiles en UNA query (eficiente para producción)
        canvas_ids = [e.get('user_id') for e in all_enrollments if e.get('user_id')]
        existing_profiles = {
            p.canvas_user_id: p 
            for p in StudentProfile.objects.filter(canvas_user_id__in=canvas_ids)
        }
        
        # Construir respuesta enriquecida
        students = []
        students_in_kairos = 0
        
        for enrollment in all_enrollments:
            user_data = enrollment.get('user', {})
            canvas_uid = enrollment.get('user_id') or user_data.get('id')
            
            if not canvas_uid:
                continue
            
            profile = existing_profiles.get(canvas_uid)
            has_session = profile is not None
            
            if has_session:
                students_in_kairos += 1
            
            students.append({
                'canvas_user_id': canvas_uid,
                'name': user_data.get('name', user_data.get('sortable_name', 'Sin nombre')),
                'email': user_data.get('email', user_data.get('login_id', '')),
                'avatar_url': user_data.get('avatar_url', ''),
                'has_kairos_session': has_session,
                'total_logins': profile.total_logins if has_session else 0,
                'logins_this_week': profile.logins_this_week() if has_session else 0,
                'first_login': profile.first_login_at.strftime('%Y-%m-%d %H:%M') if has_session else None,
                'last_login': profile.last_login_at.strftime('%Y-%m-%d %H:%M') if has_session else None,
            })
        
        # Ordenar: primero los que tienen sesión en Kairos, luego por nombre
        students.sort(key=lambda s: (not s['has_kairos_session'], s['name'].lower()))
        
        return JsonResponse({
            'status': 'ok',
            'course_name': course.name,
            'students': students,
            'total_students': len(students),
            'students_in_kairos': students_in_kairos,
        })
        
    except CanvasToken.DoesNotExist:
        return JsonResponse({'error': 'Token de Canvas no encontrado'}, status=401)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Curso no encontrado'}, status=404)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Canvas enrollments for course {course_id}: {e}")
        return JsonResponse({'error': f'Error de conexión con Canvas: {str(e)}'}, status=502)
    except Exception as e:
        logger.error(f"Error in api_teacher_course_students: {e}", exc_info=True)
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)


# ============================================================================
# TEACHER AI — Generador de tareas con IA
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_teacher_ai_generate(request, course_id):
    """
    API: El profesor describe la tarea → DeepSeek genera la propuesta.
    
    POST body (JSON):
        { "prompt": "simple, tres ejercicios, con razonamiento crítico" }
    
    Response:
        {
            "description": "...texto generado por IA...",
            "tokens_used": 450,
            "processing_time": 2.3,
            "model": "deepseek-chat"
        }
    """
    try:
        canvas_token = request.user.canvas_token
        if not canvas_token.is_teacher():
            return JsonResponse({'error': 'Acceso restringido a profesores'}, status=403)

        course = Course.objects.get(id=course_id, user=request.user)

        body = json.loads(request.body)
        prompt = body.get('prompt', '').strip()
        if not prompt:
            return JsonResponse({'error': 'El campo "prompt" es obligatorio'}, status=400)

        from .teacher_ai_service import get_teacher_ai_service
        ai = get_teacher_ai_service()
        result = ai.generate_assignment(
            teacher_prompt=prompt,
            course_name=course.name,
        )

        return JsonResponse({
            'status': 'ok',
            'description': result['description'],
            'tokens_used': result['tokens_used'],
            'processing_time': round(result['processing_time'], 2),
            'model': result['model'],
        })

    except CanvasToken.DoesNotExist:
        return JsonResponse({'error': 'Token de Canvas no encontrado'}, status=401)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Curso no encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error in api_teacher_ai_generate: {e}", exc_info=True)
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_teacher_create_assignment(request, course_id):
    """
    API: Crea una tarea en Canvas vía Canvas API.
    
    POST body (JSON):
        {
            "name": "Tarea 1: Pensamiento Crítico",
            "description": "<p>Instrucciones...</p>",
            "due_at": "2026-03-15T23:59:00Z",    // ISO 8601 (opcional)
            "points_possible": 100,                // (opcional, default 0)
            "submission_types": ["online_text_entry", "online_upload"],  // (opcional)
            "assignment_group_id": 12345,          // (opcional)
            "published": false                     // (opcional, default false)
        }
    
    Canvas submission_types válidos:
        online_text_entry, online_upload, online_url, media_recording, none
    
    Response:
        { "status": "ok", "assignment": { ...canvas assignment object... } }
    """
    try:
        canvas_token = request.user.canvas_token
        if not canvas_token.is_teacher():
            return JsonResponse({'error': 'Acceso restringido a profesores'}, status=403)

        course = Course.objects.get(id=course_id, user=request.user)

        body = json.loads(request.body)
        name = body.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'El nombre de la tarea es obligatorio'}, status=400)

        # Construir payload para Canvas API
        assignment_data = {
            'assignment[name]': name,
            'assignment[description]': body.get('description', ''),
            'assignment[published]': 'true' if body.get('published', False) else 'false',
        }

        # Campos opcionales
        if body.get('due_at'):
            assignment_data['assignment[due_at]'] = body['due_at']
        if body.get('lock_at'):
            assignment_data['assignment[lock_at]'] = body['lock_at']
        if body.get('unlock_at'):
            assignment_data['assignment[unlock_at]'] = body['unlock_at']

        points = body.get('points_possible')
        if points is not None:
            assignment_data['assignment[points_possible]'] = str(points)

        submission_types = body.get('submission_types', ['online_text_entry'])
        for st in submission_types:
            assignment_data.setdefault('assignment[submission_types][]', [])
        # Canvas expects repeated keys for arrays
        submission_list = body.get('submission_types', ['online_text_entry'])

        if body.get('assignment_group_id'):
            assignment_data['assignment[assignment_group_id]'] = str(body['assignment_group_id'])

        # Obtener token válido de Canvas
        from .canvas_auth import get_valid_canvas_token
        access_token = get_valid_canvas_token(request.user)
        if not access_token:
            return JsonResponse({'error': 'Token de Canvas expirado'}, status=401)

        headers = {'Authorization': f'Bearer {access_token}'}
        canvas_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses/{course.canvas_course_id}/assignments"

        # Canvas API expects form-encoded data for arrays, build properly
        payload = {
            'assignment[name]': name,
            'assignment[description]': body.get('description', ''),
            'assignment[published]': body.get('published', False),
        }
        if body.get('due_at'):
            payload['assignment[due_at]'] = body['due_at']
        if body.get('lock_at'):
            payload['assignment[lock_at]'] = body['lock_at']
        if body.get('unlock_at'):
            payload['assignment[unlock_at]'] = body['unlock_at']
        if points is not None:
            payload['assignment[points_possible]'] = points
        if body.get('assignment_group_id'):
            payload['assignment[assignment_group_id]'] = body['assignment_group_id']

        # submission_types needs special handling (array parameter)
        response = requests.post(
            canvas_url,
            headers=headers,
            data={
                **{k: v for k, v in payload.items()},
                'assignment[submission_types][]': submission_list,
            },
        )
        response.raise_for_status()

        canvas_assignment = response.json()

        logger.info(
            f"Teacher {request.user.username} created assignment "
            f"'{name}' in course {course.canvas_course_id} "
            f"(Canvas ID: {canvas_assignment.get('id')})"
        )

        return JsonResponse({
            'status': 'ok',
            'assignment': {
                'id': canvas_assignment.get('id'),
                'name': canvas_assignment.get('name'),
                'html_url': canvas_assignment.get('html_url'),
                'due_at': canvas_assignment.get('due_at'),
                'points_possible': canvas_assignment.get('points_possible'),
                'published': canvas_assignment.get('published'),
            }
        })

    except CanvasToken.DoesNotExist:
        return JsonResponse({'error': 'Token de Canvas no encontrado'}, status=401)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Curso no encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except requests.exceptions.HTTPError as e:
        error_body = ''
        if e.response is not None:
            try:
                error_body = e.response.json()
            except Exception:
                error_body = e.response.text[:500]
        logger.error(f"Canvas API error creating assignment: {e} — {error_body}")
        return JsonResponse({
            'error': f'Error de Canvas al crear tarea',
            'canvas_error': str(error_body),
        }, status=e.response.status_code if e.response is not None else 502)
    except Exception as e:
        logger.error(f"Error in api_teacher_create_assignment: {e}", exc_info=True)
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET"])
def api_teacher_assignment_groups(request, course_id):
    """
    API: Obtiene los grupos de tareas del curso desde Canvas.
    El profesor los necesita para elegir en qué grupo publicar la tarea.
    
    Response:
        {
            "groups": [
                { "id": 123, "name": "Tareas", "position": 1 },
                { "id": 456, "name": "Exámenes", "position": 2 }
            ]
        }
    """
    try:
        canvas_token = request.user.canvas_token
        if not canvas_token.is_teacher():
            return JsonResponse({'error': 'Acceso restringido a profesores'}, status=403)

        course = Course.objects.get(id=course_id, user=request.user)

        from .canvas_auth import get_valid_canvas_token
        access_token = get_valid_canvas_token(request.user)
        if not access_token:
            return JsonResponse({'error': 'Token de Canvas expirado'}, status=401)

        headers = {'Authorization': f'Bearer {access_token}'}
        url = f"{settings.CANVAS_BASE_URL}/api/v1/courses/{course.canvas_course_id}/assignment_groups"

        resp = requests.get(url, headers=headers, params={'per_page': 100})
        resp.raise_for_status()

        groups = [
            {'id': g['id'], 'name': g['name'], 'position': g.get('position', 0)}
            for g in resp.json()
        ]
        groups.sort(key=lambda g: g['position'])

        return JsonResponse({'status': 'ok', 'groups': groups})

    except CanvasToken.DoesNotExist:
        return JsonResponse({'error': 'Token de Canvas no encontrado'}, status=401)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Curso no encontrado'}, status=404)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching assignment groups: {e}")
        return JsonResponse({'error': f'Error de Canvas: {str(e)}'}, status=502)


# ============================================================================
# ENDPOINTS DE DEBUGGING - Para ver qué está pasando adentro del sistema
# ============================================================================

@login_required
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


@login_required
@require_http_methods(["GET"])
def debug_stats(request):
    """
    Endpoint para obtener estadísticas del sistema.
    Incluye stats de RAG (AHORA desde BD, no en-memoria), DeepSeek, memoria, etc.
    """
    try:
        debug_service = get_debug_service()
        stats = debug_service.get_stats()
        
        # Obtener embeddings REALES de la BD (query eficiente, sin N+1)
        from django.db.models import Count, Q
        embedding_stats = ModuleEmbedding.objects.aggregate(
            total_modules=Count('id'),
        )
        
        # Contar documentos: necesitamos iterar pero con una sola query
        total_embeddings = 0
        analyzed_modules = 0
        for emb in ModuleEmbedding.objects.only('embedding_data').iterator():
            docs = emb.embedding_data.get('documents', []) if emb.embedding_data else []
            doc_count = len(docs)
            if doc_count > 0:
                total_embeddings += doc_count
                analyzed_modules += 1
        
        # Actualizar stats de RAG con datos REALES de BD
        stats['rag']['total_embeddings'] = total_embeddings
        stats['rag']['modules_analyzed'] = analyzed_modules
        
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


@login_required
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


@login_required
@require_http_methods(["GET"])
def debug_rag_status(request):
    """
    Endpoint para ver el estado actual del sistema RAG.
    Muestra: ChromaDB status, embedding counts, backend being used, etc.
    """
    try:
        rag_service = get_rag_service()
        
        # Información del backend
        info = {
            'backend': 'chromadb' if rag_service.using_chromadb else 'in_memory',
            'chromadb_available': bool(rag_service.client),
            'persistent_dir': rag_service.persistent_dir if rag_service.using_chromadb else None,
            'embedding_model': 'paraphrase-multilingual-MiniLM-L12-v2',
        }
        
        # Si es ChromaDB, contar colecciones
        if rag_service.using_chromadb and rag_service.client:
            try:
                collections = rag_service.client.list_collections()
                collections_info = []
                for col in collections:
                    count = col.count()
                    collections_info.append({
                        'name': col.name,
                        'embeddings_count': count
                    })
                info['collections'] = collections_info
                info['total_collections'] = len(collections)
                info['total_embeddings'] = sum(c['embeddings_count'] for c in collections_info)
            except Exception as e:
                logger.error(f"Error listing ChromaDB collections: {e}")
                info['collections'] = []
                info['error'] = str(e)
        else:
            # Mostrar información de memoria
            info['in_memory_collections'] = list(rag_service.in_memory_db.keys())
            info['total_embeddings'] = sum(
                len(rag_service.in_memory_db[k].get('embeddings', []))
                for k in rag_service.in_memory_db
            )
        
        # Agregar versión del código para diagnóstico
        info['code_version'] = '2026-03-08-v3-clean-chunking'
        info['similarity_formula'] = '1 - (distance / 2)'
        
        return JsonResponse({
            'status': 'ok',
            'rag_status': info
        })
    except Exception as e:
        logger.error(f"Error in debug_rag_status: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def debug_search_test(request):
    """
    Endpoint de diagnóstico para probar búsqueda RAG con detalles crudos.
    Muestra distancias originales de ChromaDB y cómo se calculan las similitudes.
    
    Uso: /api/debug/search-test/?q=resumen&module_id=1&course_id=1
    """
    try:
        query = request.GET.get('q', 'Dame un resumen')
        module_id = int(request.GET.get('module_id', 1))
        course_id = int(request.GET.get('course_id', 1))
        top_k = int(request.GET.get('top_k', 5))
        
        rag_service = get_rag_service()
        collection_name = f"module_{module_id}_course_{course_id}"
        
        result = {
            'query': query,
            'module_id': module_id,
            'course_id': course_id,
            'top_k': top_k,
            'collection_name': collection_name,
            'code_version': '2026-03-08-v3-clean-chunking',
        }
        
        if rag_service.using_chromadb and rag_service.client:
            try:
                collection = rag_service.client.get_collection(collection_name)
                total_docs = collection.count()
                result['total_docs_in_collection'] = total_docs
                
                raw_results = collection.query(
                    query_texts=[query],
                    n_results=min(top_k, total_docs),
                    include=["documents", "metadatas", "distances"]
                )
                
                result['raw_distances'] = raw_results.get('distances', [[]])[0]
                
                # Mostrar cómo se calcula cada similitud
                items = []
                if raw_results['documents'] and raw_results['documents'][0]:
                    for i, (doc, meta, dist) in enumerate(zip(
                        raw_results['documents'][0],
                        raw_results['metadatas'][0],
                        raw_results['distances'][0]
                    )):
                        # Fórmula correcta
                        similarity_correct = max(0, 1 - (dist / 2))
                        # Fórmula incorrecta (vieja)
                        similarity_wrong = 1 - dist
                        
                        items.append({
                            'rank': i + 1,
                            'title': meta.get('item_title', 'Unknown'),
                            'distance': round(dist, 4),
                            'similarity_correct': round(similarity_correct, 4),
                            'similarity_wrong': round(similarity_wrong, 4),
                            'preview': doc[:100] + '...'
                        })
                
                result['items'] = items
                result['diagnosis'] = 'Si ves similarity_wrong en el dashboard, el servidor no está actualizado'
                
            except Exception as e:
                result['error'] = str(e)
        else:
            result['error'] = 'ChromaDB not available'
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in debug_search_test: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def debug_prompt_flow(request):
    """
    Endpoint para obtener el último flujo de prompt.
    Muestra: pregunta, embeddings recuperados, contexto y respuesta.
    
    UTILIZADO POR: /debug/dashboard/ - Actualiza en tiempo real cada 2 segundos
    
    Retorna:
    {
        'last_question': str,
        'question_length': int,
        'retrieved_count': int,
        'retrieved_docs': [
            {
                'rank': int,                    # Posición en ranking
                'title': str,                   # Título del documento
                'similarity': float (0.0-1.0),  # Puntuación de similitud
                'preview': str                  # Primeros 150 caracteres
            },
            ...
        ],
        'rag_context': str,                    # Contexto formateado para DeepSeek
        'deepseek_response': str,              # Respuesta del modelo
        'timestamp': str                       # ISO format timestamp
    }
    """
    global _last_prompt_flow
    
    # Incluir info del query_analysis si está disponible
    query_analysis = _last_prompt_flow.get('query_analysis', {})
    
    return JsonResponse({
        'status': 'ok',
        'last_question': _last_prompt_flow.get('question') or 'Sin pregunta registrada',
        'question_length': _last_prompt_flow.get('question_length', 0),
        'query_type': query_analysis.get('query_type', 'unknown'),
        'requested_chunks': _last_prompt_flow.get('requested_chunks', 5),  # Cuántos se solicitaron
        'retrieved_count': _last_prompt_flow.get('retrieved_count', 0),   # Cuántos llegaron
        'retrieved_docs': _last_prompt_flow.get('retrieved_docs', []),
        'rag_context': _last_prompt_flow.get('context') or 'Sin contexto',
        'system_prompt': _last_prompt_flow.get('system_prompt') or 'No disponible',
        'full_user_prompt': _last_prompt_flow.get('full_user_prompt') or 'No disponible',
        'deepseek_response': _last_prompt_flow.get('response') or 'Sin respuesta registrada',
        'timestamp': _last_prompt_flow.get('timestamp') or '?'
    })


@login_required
@require_http_methods(["POST"])
def debug_question_embeddings(request):
    """
    Endpoint para ver los embeddings de una pregunta y compararlos con documentos analizados.
    
    POST body:
    {
        "question": "¿Qué es...",
        "module_id": 1,
        "course_id": 1
    }
    
    Retorna:
    - Embedding de la pregunta (primeras 5 dimensiones)
    - Puntuaciones de similitud con cada chunk
    - Chunks más relevantes
    """
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        module_id = data.get('module_id')
        course_id = data.get('course_id')
        
        if not question:
            return JsonResponse({'error': 'Pregunta vacía'}, status=400)
        
        # Obtener RAG service para acceder al embedding model
        rag_service = get_rag_service()
        
        # Paso 1: Crear embedding de la pregunta con Piragi
        question_embedding = rag_service.embedding_model.encode(question).tolist()
        
        # Paso 2: Obtener embeddings de los documentos analizados
        collection_name = f"module_{module_id}_course_{course_id}"
        
        if collection_name not in rag_service.in_memory_db:
            return JsonResponse({
                'error': f'No hay documentos analizados para este módulo',
                'collection': collection_name
            }, status=404)
        
        collection = rag_service.in_memory_db[collection_name]
        
        if not collection['documents']:
            return JsonResponse({
                'error': 'Colección vacía',
                'collection': collection_name
            }, status=404)
        
        # Paso 3: Calcular similitud coseno entre pregunta y cada chunk
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = [
                float(cosine_similarity([question_embedding], [emb])[0][0])
                for emb in collection['embeddings']
            ]
        except ImportError:
            import numpy as np
            query_norm = np.linalg.norm(question_embedding)
            similarities = []
            for emb in collection['embeddings']:
                emb_norm = np.linalg.norm(emb)
                similarity = float(np.dot(question_embedding, emb) / (query_norm * emb_norm + 1e-8))
                similarities.append(similarity)
        
        # Ordenar por similitud
        ranked_chunks = []
        for idx, (doc, metadata, similarity) in enumerate(zip(
            collection['documents'],
            collection['metadatas'],
            similarities
        )):
            ranked_chunks.append({
                'rank': idx + 1,
                'similarity': similarity,
                'title': metadata.get('item_title', 'Unknown'),
                'chunk_index': metadata.get('chunk_index', '0'),
                'chunk_total': metadata.get('chunk_total', '1'),
                'preview': doc[:200],
                'full_content': doc,
            })
        
        # Ordenar por similitud (descendente)
        ranked_chunks.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Sacar top 5
        top_chunks = ranked_chunks[:5]
        
        return JsonResponse({
            'status': 'ok',
            'question': question,
            'question_embedding_dims': len(question_embedding),
            'question_embedding_sample': question_embedding[:5],  # Primeras 5 dimensiones como muestra
            'total_chunks_analyzed': len(collection['documents']),
            'similarities': {
                'min': round(min(similarities), 3),
                'max': round(max(similarities), 3),
                'mean': round(sum(similarities) / len(similarities), 3),
            },
            'top_matches': top_chunks,
            'all_chunks': ranked_chunks  # Todos ordenados por similitud
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error en debug_question_embeddings: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET", "POST"])
def test_button_click(request):
    """
    Endpoint para testear que los clics del botón funcionan correctamente.
    Útil para debugging sin necesidad de análisis real.
    
    GET: Retorna info de test
    POST: Simula un análisis (sin hacer nada, solo retorna OK)
    """
    if request.method == 'GET':
        return JsonResponse({
            'status': 'ok',
            'message': 'Test button endpoint is working',
            'usage': 'POST para simular clic del botón',
            'response_time_ms': 10
        })
    
    # POST - Simular análisis
    logger.info(f"Test button click from {request.META.get('REMOTE_ADDR', 'unknown')}")
    import time
    time.sleep(1)  # Simular pequeña demora
    
    return JsonResponse({
        'status': 'completed',
        'message': 'Test análisis completado (simulado)',
        'items_processed': 5,
        'test': True
    })


@login_required
@require_http_methods(["GET"])
def check_module_analysis_status(request, module_id):
    """
    Endpoint para verificar el estado de análisis de un módulo.
    
    Checkea ModuleEmbedding en BD (compatible con cloud: PostgreSQL, Oracle).
    
    Respuesta:
    {
        'is_analyzed': True/False,
        'analysis_status': 'completed'/'analyzing'/'failed'/'not_analyzed'
        'items_count': N,
        'has_embeddings_in_db': bool
    }
    """
    
    try:
        module = Module.objects.select_related('course').get(id=module_id)
        
        # Obtener estado de BD
        try:
            analysis = ModuleAnalysis.objects.get(module=module)
            db_status = analysis.status
        except ModuleAnalysis.DoesNotExist:
            db_status = 'not_analyzed'
        
        # Checkear si existen embeddings en BD
        has_embeddings_in_db = False
        try:
            embedding = ModuleEmbedding.objects.get(module=module)
            docs = embedding.embedding_data.get('documents', []) if embedding.embedding_data else []
            has_embeddings_in_db = len(docs) > 0
        except ModuleEmbedding.DoesNotExist:
            has_embeddings_in_db = False
        
        # Considerar analizado si el status es 'completed' O hay embeddings en BD
        is_analyzed = (db_status == 'completed') or has_embeddings_in_db
        
        return JsonResponse({
            'status': 'ok',
            'module_id': module_id,
            'is_analyzed': is_analyzed,
            'analysis_status': db_status,
            'items_count': module.items.count(),
            'has_embeddings_in_db': has_embeddings_in_db
        })
    
    except Module.DoesNotExist:
        return JsonResponse({
            'status': 'ok',
            'module_id': module_id,
            'is_analyzed': False,
            'items_count': 0,
            'has_embeddings_in_db': False,
            'analysis_status': 'not_found'
        })
    except Exception as e:
        logger.error(f"Error checking analysis status: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_all_modules_stats(request):
    """
    Endpoint para obtener el estado de TODOS los módulos y sus embeddings.
    Usado por: Dashboard, Botones, cualquier componente que necesite ver estado real.
    Lee de ChromaDB primero, fallback a Django DB.
    """
    try:
        modules = Module.objects.select_related('course').prefetch_related('embedding').all()
        total_embeddings = 0
        modules_data = []
        
        # Intentar usar ChromaDB para stats reales
        chromadb_available = False
        chromadb_collections = {}
        try:
            rag_service = get_rag_service()
            if rag_service.using_chromadb and rag_service.client:
                chromadb_available = True
                # Obtener todas las colecciones de ChromaDB
                all_collections = rag_service.client.list_collections()
                for coll in all_collections:
                    chromadb_collections[coll.name] = coll.count()
                logger.debug(f"[STATS] ChromaDB collections: {chromadb_collections}")
        except Exception as e:
            logger.warning(f"[STATS] ChromaDB not available: {e}")
        
        for module in modules:
            doc_count = 0
            
            # Primero intentar ChromaDB
            if chromadb_available:
                collection_name = f"module_{module.id}_course_{module.course_id}"
                if collection_name in chromadb_collections:
                    doc_count = chromadb_collections[collection_name]
            
            # Fallback a Django DB si ChromaDB no tiene datos
            if doc_count == 0:
                try:
                    embedding = module.embedding
                    docs = embedding.embedding_data.get('documents', []) if embedding.embedding_data else []
                    doc_count = len(docs)
                except ModuleEmbedding.DoesNotExist:
                    doc_count = 0
            
            total_embeddings += doc_count
            has_embeddings = doc_count > 0
            button_text = '🔄 Re-analizar' if has_embeddings else '🔍 Analizar'
            
            modules_data.append({
                'id': module.id,
                'name': module.name,
                'embeddings_count': doc_count,
                'has_embeddings': has_embeddings,
                'button_text': button_text
            })
        
        return JsonResponse({
            'status': 'ok',
            'timestamp': str(timezone.now()),
            'total_modules': modules.count(),
            'total_embeddings': total_embeddings,
            'modules': modules_data,
            'chromadb_active': chromadb_available
        })
    except Exception as e:
        logger.error(f"Error getting all modules stats: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def debug_test_data(request):
    """
    Endpoint para generar datos de prueba en el debug dashboard.
    Útil para ver cómo se ve el dashboard con datos reales.
    """
    global _last_prompt_flow
    
    # Generar datos de prueba
    mock_data = {
        'question': '¿Cuál es el propósito principal del aprendizaje automático en sistemas educativos?',
        'retrieved_count': 3,
        'retrieved_docs': [
            {
                'rank': 1,
                'title': 'Introduction to Machine Learning',
                'similarity': 0.945,
                'preview': 'El aprendizaje automático es una rama de la inteligencia artificial que permite que las máquinas aprendan de los datos sin ser programadas explícitamente...'
            },
            {
                'rank': 2,
                'title': 'ML Applications in Education',
                'similarity': 0.872,
                'preview': 'Las aplicaciones del aprendizaje automático en educación transforman la forma en que los estudiantes aprenden. Desde sistemas de recomendación personalizados...'
            },
            {
                'rank': 3,
                'title': 'Neural Networks Basics',
                'similarity': 0.756,
                'preview': 'Las redes neuronales son modelos computacionales inspirados en el cerebro humano. Consisten en capas de neuronas artificiales conectadas...'
            }
        ],
        'context': '''[Docs 1] Introduction to Machine Learning
El aprendizaje automático es una rama de la inteligencia artificial que permite que las máquinas aprendan de los datos sin ser programadas explícitamente. Mediante algoritmos y técnicas estadísticas, los sistemas de ML pueden identificar patrones, hacer predicciones y mejorar continuamente.

[Docs 2] ML Applications in Education
Las aplicaciones del aprendizaje automático en educación transforman la forma en que los estudiantes aprenden. Desde sistemas de recomendación personalizados hasta análisis predictivo del rendimiento estudiantil, el ML permite una educación más adaptativa y personalizada.

[Docs 3] Neural Networks Basics
Las redes neuronales son modelos computacionales inspirados en el cerebro humano. Consisten en capas de neuronas artificiales conectadas mediante pesos sinápticos, permitiendo el aprendizaje profundo y procesamiento complejo de datos.''',
        'response': 'El aprendizaje automático juega un papel crucial en los sistemas educativos modernos. Como se puede ver en los documentos recuperados, el ML permite personalizar la experiencia de aprendizaje para cada estudiante, predecir problemas académicos y adaptar dinámicamente el contenido.\n\nLos principales propósitos incluyen:\n\n1. **Personalización**: Los sistemas de ML pueden adaptar el contenido y la velocidad de aprendizaje a las necesidades individuales de cada estudiante.\n\n2. **Predicción de Rendimiento**: Mediante el análisis de patrones históricos, se pueden identificar estudiantes que podrían necesitar apoyo adicional.\n\n3. **Optimización de Recursos**: El ML ayuda a instituciones a asignar recursos educativos de manera más eficiente.\n\n4. **Retroalimentación Inmediata**: Los sistemas pueden proporcionar feedback instantáneo sobre el desempeño del estudiante.\n\nEsta integración de tecnología ML en educación representa un cambio fundamental hacia sistemas más inteligentes, adaptativos y centrados en el estudiante.',
        'timestamp': timezone.now().isoformat()
    }
    
    _last_prompt_flow = mock_data
    
    return JsonResponse({
        'status': 'ok',
        'message': 'Datos de prueba generados exitosamente en _last_prompt_flow',
        'docs_count': len(mock_data['retrieved_docs']),
        'timestamp': mock_data['timestamp']
    })


@login_required
def debug_dashboard(request):
    """
    Dashboard visual para ver qué está pasando en el sistema.
    Muestra eventos en tiempo real, estadísticas, etc.
    """
    return render(request, 'tu_app/debug_dashboard.html')


def test_button_page(request):
    """
    Página de test para debugging del botón de análisis.
    """
    return render(request, 'tu_app/test_button.html')


# ============================================================================
# EXTENSIÓN DE CHROME — Endpoints para la extensión de Kairos
# ============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def extension_ask(request):
    """
    Endpoint para la extensión de Chrome.
    Recibe texto seleccionado y devuelve respuesta RAG.
    CSRF exempt porque las requests vienen del service worker de la extensión.
    Autenticación por sesión (cookie sessionid).
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado', 'authenticated': False}, status=401)

    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        canvas_course_id = data.get('canvas_course_id')
        b64_image = data.get('image_base64', '')

        # OCR screenshot/image if provided
        image_ocr_text = None
        ocr_error = None
        if b64_image:
            try:
                from .ocr_service import get_ocr_service
                ocr = get_ocr_service()
                image_ocr_text = ocr.extract_text_from_base64(b64_image)
                logger.info(f"[EXT] Image OCR: {len(image_ocr_text)} chars")
            except Exception as e:
                ocr_error = str(e)
                logger.error(f"[EXT] Image OCR failed: {e}", exc_info=True)

        # Combine text + image OCR
        if image_ocr_text:
            if text:
                text = f"{text}\n\n[Contenido de la imagen]:\n{image_ocr_text}"
            else:
                text = f"Analiza la siguiente imagen:\n\n{image_ocr_text}"
        elif b64_image and not text:
            detail = f" Error OCR: {ocr_error}" if ocr_error else ""
            text = f"El usuario envió una imagen pero no se pudo extraer texto.{detail}"

        if not text:
            return JsonResponse({'error': 'Texto vacío'}, status=400)

        # Buscar curso por canvas_course_id si se proporcionó
        course = None
        if canvas_course_id:
            course = Course.objects.filter(
                canvas_course_id=canvas_course_id,
                user=request.user
            ).first()

        # Si no hay curso, usar el primer curso del usuario
        if not course:
            course = Course.objects.filter(user=request.user).first()

        if not course:
            return JsonResponse({'error': 'No se encontró un curso asociado'}, status=404)

        # RAG pipeline (misma lógica que chat_api)
        rag_service = get_rag_service()
        query_analyzer = get_query_analyzer(rag_service.embedding_model)
        query_analysis = query_analyzer.analyze(text)

        optimal_fragments = query_analysis['num_fragments']
        query_type = query_analysis['query_type']

        context = []
        fragments_per_module = max(2, optimal_fragments // max(1, course.modules.count()))
        for mod in course.modules.all():
            mod_context = rag_service.search_context(
                text, mod.id, course.id,
                top_k=fragments_per_module,
                query_type=query_type
            )
            context.extend(mod_context)

        # Construir contexto limpio
        import re as _re
        context_text = ""
        for i, item in enumerate(context):
            if isinstance(item, dict):
                raw = item.get('content', '')
                clean = _re.sub(r'\n*---\s*Slide\s*\d+\s*---\n*', '\n', raw)
                clean = _re.sub(r'\n*---\s*Página\s*\d+\s*---\n*', '\n', clean)
                lines = [l.strip() for l in clean.split('\n')
                         if l.strip() and len(l.strip()) >= 3
                         and not _re.match(r'^\d{1,3}$', l.strip())
                         and not _re.match(r'^20[\dXx]{2}$', l.strip())
                         and not _re.search(r'pie de p[aá]gina|footer|placeholder|click to edit|haga clic', l, _re.IGNORECASE)]
                clean = '\n'.join(lines).strip()
                if clean and len(clean) >= 15:
                    title = item.get('metadata', {}).get('item_title', '')
                    context_text += f"\n[Doc {i+1}] {title}\n{clean}"

        # Obtener respuesta de IA
        ai_service = get_ai_service()
        start_time = time.time()
        ai_response = ai_service.answer_question(
            question=text,
            context=context,
            user=request.user
        )
        processing_time = time.time() - start_time

        answer = ai_response.get('answer', '')
        tokens = ai_response.get('tokens_used', 0)

        # Limpiar respuesta
        try:
            from textwrap import dedent
            if answer:
                answer = dedent(answer).strip()
                answer = '\n'.join(l.rstrip() for l in answer.splitlines())
                answer = _re.sub(r'\n{3,}', '\n\n', answer)
        except Exception:
            pass

        # Guardar mensaje
        ChatMessage.objects.create(
            user=request.user,
            course=course,
            module=None,
            role='student',
            content=f"[Extensión] {text}"
        )
        ChatMessage.objects.create(
            user=request.user,
            course=course,
            module=None,
            role='ai',
            content=answer,
            tokens_used=tokens,
            processing_time=processing_time,
            model_used='deepseek'
        )

        logger.info(f"[EXT] Response for {request.user.username}: {tokens} tokens, {processing_time:.2f}s")

        return JsonResponse({
            'success': True,
            'response': answer,
            'tokens_used': tokens,
            'processing_time': f'{processing_time:.2f}'
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"[EXT] Error for {request.user.username}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def extension_check_auth(request):
    """Verifica si el usuario está autenticado (para la extensión)."""
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'username': request.user.username,
        })
    return JsonResponse({'authenticated': False}, status=200)


@csrf_exempt
@require_http_methods(["GET"])
def extension_courses(request):
    """Devuelve los cursos del usuario autenticado (para la extensión)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    courses = Course.objects.filter(user=request.user).values(
        'id', 'canvas_course_id', 'name', 'code'
    )
    return JsonResponse({'courses': list(courses)})

