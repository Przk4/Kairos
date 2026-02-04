# tu_app/middleware.py

import logging
from .canvas_auth import get_valid_canvas_token

logger = logging.getLogger(__name__)


class CanvasTokenRefreshMiddleware:
    """
    Middleware que intenta refrescar automáticamente el token de Canvas
    en cada petición si el usuario está autenticado y el token está por expirar.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Si el usuario está autenticado, intentamos obtener un token válido
        if request.user.is_authenticated:
            try:
                # Esta función refrescará automáticamente si es necesario
                get_valid_canvas_token(request.user)
            except Exception as e:
                logger.warning(f"Error in CanvasTokenRefreshMiddleware for user {request.user.username}: {str(e)}")
        
        response = self.get_response(request)
        return response
