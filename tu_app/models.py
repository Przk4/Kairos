from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class CanvasToken(models.Model):
    """
    Modelo para guardar los tokens de Canvas de cada usuario.
    Permite reautenticación automática sin pedir permisos de nuevo.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='canvas_token')
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    canvas_user_id = models.IntegerField()  # Canvas user ID (renombrado para evitar conflicto)
    expires_at = models.DateTimeField()
    scopes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_expired(self):
        """Verifica si el token ha expirado."""
        return timezone.now() >= self.expires_at
    
    def needs_refresh(self, buffer_minutes=5):
        """Verifica si el token necesita refrescarse (con buffer de seguridad)."""
        refresh_time = self.expires_at - timezone.timedelta(minutes=buffer_minutes)
        return timezone.now() >= refresh_time
    
    def __str__(self):
        return f"Canvas Token for {self.user.username}"
    
    class Meta:
        verbose_name = "Canvas Token"
        verbose_name_plural = "Canvas Tokens"
