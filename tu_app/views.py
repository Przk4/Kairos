# tu_app/views.py

from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import requests
import logging

def index(request):
    """
    Página principal. Muestra el botón de login o la lista de cursos si ya está conectado.
    """
    access_token = request.session.get('canvas_access_token')
    courses = None
    error_message = None

    if access_token:
        # Idea profesional: Comprobar si el token ha expirado antes de usarlo.
        # (Esto requeriría guardar la fecha de expiración en la sesión).
        
        # Idea profesional: Comprobar si tenemos el scope necesario.
        required_scope = 'url:GET|/api/v1/courses'
        granted_scopes = request.session.get('canvas_scopes', '')
        if required_scope not in granted_scopes:
            error_message = "No se concedió el permiso para ver los cursos. Por favor, vuelve a iniciar sesión."
            # Limpiamos la sesión para forzar un nuevo login con los scopes correctos.
            request.session.flush()

        headers = {'Authorization': f'Bearer {access_token}'}
        api_url = f"{settings.CANVAS_BASE_URL}/api/v1/courses"
        
        try:
            response = requests.get(api_url, headers=headers, params={'enrollment_state': 'active'})
            response.raise_for_status()  # Lanza un error si la respuesta es 4xx o 5xx
            courses = response.json()
        except requests.exceptions.RequestException as e:
            error_message = f"Error al obtener los cursos. El token puede haber expirado. Por favor, intenta conectar de nuevo."
            # Limpiamos el token inválido de la sesión
            request.session.flush() # Limpia toda la sesión si el token falla
    
    return render(request, 'tu_app/index.html', {
        'is_authenticated': access_token is not None,
        'courses': courses,
        'error_message': error_message,
        'user_id': request.session.get('canvas_user_id')
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
        # Añadimos el scope para solicitar permiso para leer la lista de cursos.
        # Esto es necesario para evitar el error "invalid_scope".
        f"&scope=url:GET|/api/v1/courses"
    )
    return redirect(auth_url)

def canvas_callback(request):
    """
    Paso 2 del flujo: Canvas nos redirige aquí con un código.
    Lo intercambiamos por un token de acceso.
    """
    auth_code = request.GET.get('code')
    if not auth_code:
        return render(request, 'tu_app/error.html', {'error': 'No se recibió el código de autorización.'})

    # Preparamos la solicitud para obtener el token
    token_url = f"{settings.CANVAS_BASE_URL}/login/oauth2/token"
    payload = {
        'grant_type': 'authorization_code',
        'client_id': settings.CANVAS_CLIENT_ID,
        'client_secret': settings.CANVAS_CLIENT_SECRET,
        'redirect_uri': settings.CANVAS_REDIRECT_URI,
        'code': auth_code,
    }

    # Preparamos los encabezados, incluyendo el User-Agent requerido por Canvas
    headers = {
        'User-Agent': 'KairosProject/1.0 (pruzhk4)'
    }


    try:
        # Hacemos la solicitud POST
        response = requests.post(token_url, data=payload, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()

        # Guardamos toda la información útil en la sesión
        request.session['canvas_access_token'] = token_data['access_token']
        request.session['canvas_refresh_token'] = token_data.get('refresh_token')
        request.session['canvas_user_id'] = token_data['user']['id']
        request.session['canvas_scopes'] = token_data.get('scope', '')
        
        # Guardamos cuándo expira el token para poder refrescarlo en el futuro
        expires_in = token_data.get('expires_in', 3600) # Segundos
        request.session['canvas_token_expires_at'] = (timezone.now() + timedelta(seconds=expires_in)).isoformat()
        
        # Redirigimos a la página principal, donde ahora se mostrarán los cursos
        return redirect('index')

    except requests.exceptions.RequestException as e:
        # Loguear el error detallado para el desarrollador
        logger = logging.getLogger(__name__)
        response_details = e.response.text if e.response else 'No se recibió respuesta del servidor.'
        logger.error(f"Error al solicitar el token de Canvas: {e}. Detalles: {response_details}")
        
        # Mostrar un mensaje genérico al usuario
        return render(request, 'tu_app/error.html', {
            'error': 'Ocurrió un error durante la autenticación con Canvas. Por favor, inténtalo de nuevo.'
        })

def canvas_logout(request):
    """
    Limpia el token de la sesión para "desconectar".
    """
    request.session.flush() # flush() es más seguro, elimina toda la sesión.
    return redirect('index')
