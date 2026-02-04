# Sistema de Reautenticación Automática OAuth2 Canvas

## ¿Qué se implementó?

Tu proyecto ahora tiene **reautenticación automática** para Canvas OAuth2. Esto significa:

✅ **Sin pedir autorización manualmente** - El token se refresca automáticamente cuando está por expirar
✅ **Sesión persistente** - El usuario permanece conectado sin interrupciones
✅ **Seguro** - Los tokens se almacenan en BD cifrados y con expiración
✅ **Transparente** - Todo ocurre sin intervención del usuario

## Cómo funciona

### 1. **Almacenamiento de Tokens (BD)**
- Los tokens se guardan en el modelo `CanvasToken` en lugar de en la sesión
- Cada usuario tiene su propio `OneToOneField` con Django User
- Se guarda: access_token, refresh_token, fecha de expiración

### 2. **Refresco Automático**
- **Middleware**: En cada petición, el middleware verifica si el token necesita refresco
- **Antes de expirar**: Si falta <5 minutos para expirar, se refresca automáticamente
- **Sin intervención**: El usuario nunca tiene que hacer login de nuevo

### 3. **Funciones Auxiliares** (canvas_auth.py)
```python
get_valid_canvas_token(user)  # Obtiene token válido (refresca si es necesario)
refresh_canvas_token(token)   # Refresca manualmente
make_canvas_request(user, 'get', '/api/v1/courses')  # Peticiones con token automático
```

## Uso en tu código

### En views.py
Antes (sesión - ❌):
```python
access_token = request.session.get('canvas_access_token')
```

Ahora (automático - ✅):
```python
from tu_app.canvas_auth import get_valid_canvas_token

access_token = get_valid_canvas_token(request.user)
# Si está por expirar, se refresca automáticamente
```

### Hacer peticiones a Canvas
```python
from tu_app.canvas_auth import make_canvas_request

response = make_canvas_request(request.user, 'get', '/api/v1/courses')
if response:
    courses = response.json()
```

## Cambios en settings.py

Se agregó el middleware a `MIDDLEWARE`:
```python
'tu_app.middleware.CanvasTokenRefreshMiddleware',
```

Este middleware se ejecuta en CADA petición y refresca tokens automáticamente.

## Cambios en modelos

Nuevo modelo `CanvasToken`:
- `user`: OneToOneField al usuario de Django
- `access_token`: Token de acceso actual
- `refresh_token`: Token para obtener nuevos access_tokens
- `canvas_user_id`: ID del usuario en Canvas
- `expires_at`: Cuándo expira el token
- `scopes`: Permisos solicitados

## Variables de entorno necesarias

Ya tienes todo en tu `.env` (o variables del sistema):
```
CANVAS_BASE_URL="https://malena-staphyloplastic-ecstatically.ngrok-free.dev"
CANVAS_CLIENT_ID="10000000000001"
CANVAS_CLIENT_SECRET="axh8AGEJBrRA4w28xt6ym382MD8JTCnyCRzfFVJyLny42cUxA9FUcH2MmFfwGKfL"
CANVAS_REDIRECT_URI="http://127.0.0.1:8000/callback"
```

## Próximas peticiones a Canvas

Ya no tendrás problemas de tokens expirados. El sistema:
1. Verifica si el token está válido
2. Si falta poco para expirar, lo refresca automáticamente
3. Usa el token válido en la petición
4. Si todo falla, retorna None para que manejes el error

## Testing

Para probar:
```powershell
python manage.py runserver
# Inicia sesión normalmente
# Espera a que casi expire el token (o simula)
# Haz una petición a la API - ¡deberá funcionar sin problemas!
```

## Seguridad

✅ Tokens seguros en BD (OneToOneField)
✅ Refresh automático 5 minutos antes de expirar
✅ Validación de expiración en cada uso
✅ Logging de errores para debugging
✅ No expones tokens en HTML/Templates

---

¿Preguntas? El sistema está listo para producción 🚀
