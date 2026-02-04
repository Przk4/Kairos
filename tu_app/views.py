# tu_app/views.py

from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
import requests
import logging
from .models import CanvasToken, Course, Module
from .canvas_auth import (
    get_valid_canvas_token, 
    refresh_canvas_token, 
    make_canvas_request,
    detect_user_role,
    sync_courses_for_user,
    sync_modules_for_course
)

logger = logging.getLogger(__name__)


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
    """
    auth_url = (
        f"{settings.CANVAS_BASE_URL}/login/oauth2/auth"
        f"?client_id={settings.CANVAS_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.CANVAS_REDIRECT_URI}"
        f"&scope=url:GET|/api/v1/courses"
    )
    return redirect(auth_url)


def canvas_callback(request):
    """
    Paso 2 del flujo: Canvas nos redirige aquí con un código.
    Lo intercambiamos por un token de acceso y lo guardamos en BD.
    """
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
