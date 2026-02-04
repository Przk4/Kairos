from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Choicesliterales para roles de usuario
USER_ROLE_CHOICES = [
    ('student', 'Estudiante'),
    ('teacher', 'Maestro'),
    ('admin', 'Administrador'),
]


class CanvasToken(models.Model):
    """
    Modelo para guardar los tokens de Canvas de cada usuario.
    Permite reautenticación automática sin pedir permisos de nuevo.
    """
    USER_ROLE_CHOICES = [
        ('student', 'Estudiante'),
        ('teacher', 'Maestro'),
        ('admin', 'Administrador'),
        ('unknown', 'Desconocido'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='canvas_token')
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    canvas_user_id = models.IntegerField()
    expires_at = models.DateTimeField()
    scopes = models.TextField(blank=True, default='')
    role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default='unknown')  # Nuevo campo
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_expired(self):
        """Verifica si el token ha expirado."""
        return timezone.now() >= self.expires_at
    
    def needs_refresh(self, buffer_minutes=5):
        """Verifica si el token necesita refrescarse (con buffer de seguridad)."""
        refresh_time = self.expires_at - timezone.timedelta(minutes=buffer_minutes)
        return timezone.now() >= refresh_time
    
    def is_teacher(self):
        """Verifica si es maestro."""
        return self.role == 'teacher'
    
    def is_student(self):
        """Verifica si es estudiante."""
        return self.role == 'student'
    
    def __str__(self):
        return f"Canvas Token for {self.user.username} ({self.get_role_display()})"
    
    class Meta:
        verbose_name = "Canvas Token"
        verbose_name_plural = "Canvas Tokens"


class Course(models.Model):
    """
    Modelo para almacenar cursos de Canvas asociados a un usuario.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    canvas_course_id = models.IntegerField()  # ID del curso en Canvas
    name = models.CharField(max_length=500)
    code = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    enrollment_role = models.CharField(max_length=50, blank=True)  # 'StudentEnrollment', 'TeacherEnrollment', etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'canvas_course_id')
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} (Canvas ID: {self.canvas_course_id})"


class Module(models.Model):
    """
    Modelo para almacenar módulos de Canvas dentro de un curso.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    canvas_module_id = models.IntegerField()  # ID del módulo en Canvas
    name = models.CharField(max_length=500)
    position = models.IntegerField()  # Orden del módulo
    is_locked = models.BooleanField(default=False)
    unlock_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('course', 'canvas_module_id')
        ordering = ['position']
    
    def __str__(self):
        return f"Module: {self.name}"


class ModuleItem(models.Model):
    """
    Modelo para almacenar items dentro de un módulo (materiales, tareas, etc.).
    """
    ITEM_TYPE_CHOICES = [
        ('File', 'Archivo'),
        ('Page', 'Página'),
        ('Assignment', 'Tarea'),
        ('Quiz', 'Cuestionario'),
        ('Discussion', 'Discusión'),
        ('ExternalUrl', 'Enlace Externo'),
        ('ExternalTool', 'Herramienta Externa'),
        ('SubHeader', 'Encabezado'),
        ('Other', 'Otro'),
    ]
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='items')
    canvas_item_id = models.IntegerField()  # ID del item en Canvas
    title = models.CharField(max_length=500)
    item_type = models.CharField(max_length=50, choices=ITEM_TYPE_CHOICES)
    position = models.IntegerField()  # Orden dentro del módulo
    url = models.URLField(blank=True, null=True)
    content_id = models.IntegerField(blank=True, null=True)  # ID de la tarea, archivo, etc.
    is_locked = models.BooleanField(default=False)
    completion_requirement = models.CharField(max_length=50, blank=True)  # 'must_view', 'must_submit', etc.
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('module', 'canvas_item_id')
        ordering = ['position']
    
    def __str__(self):
        return f"{self.title} ({self.get_item_type_display()})"
