# tu_app/canvas_auth.py

import requests
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import CanvasToken, Course, Module, ModuleItem

logger = logging.getLogger(__name__)


def refresh_canvas_token(canvas_token):
    """
    Refresca el token de Canvas usando el refresh token.
    Actualiza automáticamente el modelo con el nuevo token.
    
    Args:
        canvas_token: Instancia de CanvasToken
    
    Returns:
        bool: True si la renovación fue exitosa, False en caso contrario
    """
    if not canvas_token.refresh_token:
        logger.warning(f"No refresh token available for user {canvas_token.user.username}")
        return False
    
    token_url = f"{settings.CANVAS_BASE_URL}/login/oauth2/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': settings.CANVAS_CLIENT_ID,
        'client_secret': settings.CANVAS_CLIENT_SECRET,
        'refresh_token': canvas_token.refresh_token,
    }
    
    headers = {
        'User-Agent': 'KairosProject/1.0 (pruzhk4)'
    }
    
    try:
        response = requests.post(token_url, data=payload, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Actualizamos el token
        canvas_token.access_token = token_data['access_token']
        canvas_token.refresh_token = token_data.get('refresh_token', canvas_token.refresh_token)
        
        # Calculamos la nueva fecha de expiración
        expires_in = token_data.get('expires_in', 3600)
        canvas_token.expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        canvas_token.save()
        logger.info(f"Token refreshed successfully for user {canvas_token.user.username}")
        return True
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error refreshing Canvas token for {canvas_token.user.username}: {str(e)}")
        return False


def get_valid_canvas_token(user):
    """
    Obtiene un token válido para el usuario.
    Si el token está a punto de expirar, lo refresca automáticamente.
    
    Args:
        user: Usuario de Django
    
    Returns:
        str: Token válido o None si no hay token o no se puede refrescar
    """
    try:
        canvas_token = user.canvas_token
    except CanvasToken.DoesNotExist:
        logger.warning(f"No Canvas token found for user {user.username}")
        return None
    
    # Si el token necesita refresco, intentamos refrescarlo
    if canvas_token.needs_refresh():
        if not refresh_canvas_token(canvas_token):
            logger.error(f"Could not refresh token for user {user.username}")
            return None
    
    # Si el token está expirado, devolvemos None
    if canvas_token.is_expired():
        logger.warning(f"Canvas token expired for user {user.username}")
        return None
    
    return canvas_token.access_token


def make_canvas_request(user, method, endpoint, **kwargs):
    """
    Hace una petición a la API de Canvas con manejo automático de tokens.
    
    Args:
        user: Usuario de Django
        method: 'get', 'post', 'put', 'delete', etc.
        endpoint: Ruta de la API (ej: '/api/v1/courses')
        **kwargs: Argumentos adicionales para requests
    
    Returns:
        Response object o None si falla
    """
    access_token = get_valid_canvas_token(user)
    
    if not access_token:
        logger.warning(f"Could not get valid Canvas token for user {user.username}")
        return None
    
    url = f"{settings.CANVAS_BASE_URL}{endpoint}"
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = f'Bearer {access_token}'
    headers['User-Agent'] = 'KairosProject/1.0 (pruzhk4)'
    
    try:
        response = getattr(requests, method.lower())(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Canvas API request failed for user {user.username}: {str(e)}")
        return None

def detect_user_role(user):
    """
    Detecta si el usuario es estudiante o maestro según sus inscripciones en Canvas.
    Actualiza el rol en CanvasToken.
    
    Args:
        user: Usuario de Django
    
    Returns:
        str: 'student', 'teacher', o 'unknown'
    """
    print(f"\n🔍 [ROLE DETECTION] Starting for user: {user.username}")
    
    try:
        canvas_token = user.canvas_token
    except CanvasToken.DoesNotExist:
        print(f"❌ [ROLE DETECTION] No Canvas token found")
        return 'unknown'
    
    access_token = get_valid_canvas_token(user)
    if not access_token:
        print(f"❌ [ROLE DETECTION] No valid token")
        return canvas_token.role
    
    # Obtenemos los cursos del usuario
    headers = {'Authorization': f'Bearer {access_token}'}
    api_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses"
    
    try:
        response = requests.get(
            api_url,
            headers=headers,
            params={'include': 'enrollments'}  # Incluye info de inscripción
        )
        response.raise_for_status()
        
        courses = response.json()
        
        # Detectamos el rol según la inscripción
        is_teacher = False
        is_student = False
        
        print(f"📚 [ROLE DETECTION] Found {len(courses)} courses")
        
        for course in courses:
            enrollments = course.get('enrollments', [])
            print(f"   📖 Course: {course.get('name')} - Enrollments: {len(enrollments)}")
            
            for enrollment in enrollments:
                role = enrollment.get('role', '')
                print(f"      👤 Role: {role}")
                
                if 'TeacherEnrollment' in role or 'Teacher' in role:
                    is_teacher = True
                    print(f"      ✅ TEACHER DETECTED")
                elif 'StudentEnrollment' in role or 'Student' in role:
                    is_student = True
                    print(f"      ✅ STUDENT DETECTED")
        
        # Priorizamos estudiante sobre maestro si tiene ambos roles
        if is_student:
            new_role = 'student'
        elif is_teacher:
            new_role = 'teacher'
        else:
            new_role = 'unknown'
        
        # Guardamos el rol detectado
        canvas_token.role = new_role
        canvas_token.save()
        
        print(f"✅ [ROLE DETECTION] User {user.username} set to: {new_role}")
        print(f"   is_teacher={is_teacher}, is_student={is_student}\n")
        return new_role
        
    except requests.exceptions.RequestException as e:
        print(f"❌ [ROLE DETECTION] Error: {str(e)}")
        logger.error(f"Error detecting user role: {str(e)}")
        return canvas_token.role


def sync_courses_for_user(user):
    """
    Sincroniza todos los cursos del usuario desde Canvas a la BD.
    
    Args:
        user: Usuario de Django
    
    Returns:
        list: Lista de Course objects creados/actualizados
    """
    access_token = get_valid_canvas_token(user)
    
    if not access_token:
        logger.warning(f"Could not get valid token for user {user.username}")
        return []
    
    headers = {'Authorization': f'Bearer {access_token}'}
    api_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses"
    
    try:
        response = requests.get(
            api_url,
            headers=headers,
            params={
                'enrollment_state': 'active',
                'include': 'enrollments'
            }
        )
        response.raise_for_status()
        
        courses_data = response.json()
        synced_courses = []
        
        for course_data in courses_data:
            course, created = Course.objects.update_or_create(
                user=user,
                canvas_course_id=course_data['id'],
                defaults={
                    'name': course_data.get('name', ''),
                    'code': course_data.get('course_code', ''),
                    'description': course_data.get('public_description', ''),
                    'enrollment_role': course_data.get('enrollments', [{}])[0].get('role', ''),
                }
            )
            synced_courses.append(course)
        
        logger.info(f"Synced {len(synced_courses)} courses for user {user.username}")
        return synced_courses
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error syncing courses for user {user.username}: {str(e)}")
        return []


def sync_modules_for_course(user, course):
    """
    Sincroniza todos los módulos y sus items de un curso.
    
    Args:
        user: Usuario de Django
        course: Instancia de Course
    
    Returns:
        list: Lista de Module objects creados/actualizados
    """
    access_token = get_valid_canvas_token(user)
    
    if not access_token:
        logger.warning(f"Could not get valid token for user {user.username}")
        return []
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Primero obtenemos los módulos
    modules_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses/{course.canvas_course_id}/modules"
    
    try:
        response = requests.get(modules_url, headers=headers)
        response.raise_for_status()
        
        modules_data = response.json()
        synced_modules = []
        
        for module_data in modules_data:
            module, created = Module.objects.update_or_create(
                course=course,
                canvas_module_id=module_data['id'],
                defaults={
                    'name': module_data.get('name', ''),
                    'position': module_data.get('position', 0),
                    'is_locked': module_data.get('state') == 'locked',
                    'unlock_at': module_data.get('unlock_at'),
                }
            )
            synced_modules.append(module)
            
            # Ahora sincronizamos los items de cada módulo
            sync_module_items(user, module, headers)
        
        logger.info(f"Synced {len(synced_modules)} modules for course {course.name}")
        return synced_modules
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error syncing modules for course {course.name}: {str(e)}")
        return []


def sync_module_items(user, module, headers):
    """
    Sincroniza los items (materiales, tareas, etc.) de un módulo.
    
    Args:
        user: Usuario de Django
        module: Instancia de Module
        headers: Headers con Authorization para requests
    """
    items_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses/{module.course.canvas_course_id}/modules/{module.canvas_module_id}/items"
    
    try:
        response = requests.get(items_url, headers=headers)
        response.raise_for_status()
        
        items_data = response.json()
        
        for item_data in items_data:
            # Mapeo de tipos de Canvas a nuestros tipos
            type_map = {
                'File': 'File',
                'Page': 'Page',
                'Assignment': 'Assignment',
                'Quiz': 'Quiz',
                'Discussion': 'Discussion',
                'ExternalUrl': 'ExternalUrl',
                'ExternalTool': 'ExternalTool',
                'SubHeader': 'SubHeader',
            }
            
            item_type = type_map.get(item_data.get('type', 'Other'), 'Other')
            
            ModuleItem.objects.update_or_create(
                module=module,
                canvas_item_id=item_data['id'],
                defaults={
                    'title': item_data.get('title', ''),
                    'item_type': item_type,
                    'position': item_data.get('position', 0),
                    'url': item_data.get('url', ''),
                    'content_id': item_data.get('content_id'),
                    'is_locked': item_data.get('completion_requirement', {}).get('type') is not None,
                    'completion_requirement': item_data.get('completion_requirement', {}).get('type', ''),
                }
            )
        
        logger.info(f"Synced {len(items_data)} items for module {module.name}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error syncing module items: {str(e)}")