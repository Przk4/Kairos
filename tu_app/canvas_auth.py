# tu_app/canvas_auth.py

import requests
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import CanvasToken

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
