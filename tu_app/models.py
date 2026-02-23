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

class ModuleAnalysis(models.Model):
    """
    Tracking de análisis de módulos con Piragi + embeddings.
    Almacena metadatos sobre qué módulos han sido procesados.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('analyzing', 'Analizando'),
        ('completed', 'Completado'),
        ('failed', 'Error'),
    ]
    
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name='analysis')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    vector_db_path = models.CharField(max_length=500, blank=True)  # Ruta o ID en ChromaDB
    total_items_processed = models.IntegerField(default=0)
    embedding_model = models.CharField(max_length=100, default='sentence-transformers/all-MiniLM-L6-v2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"Analysis: {self.module.name} - {self.status}"
    
    class Meta:
        verbose_name = "Module Analysis"
        verbose_name_plural = "Module Analyses"


class ModuleEmbedding(models.Model):
    """
    Almacena embeddings de módulos en la BD.
    Compatible con:
    - SQLite (JSONField) en desarrollo local
    - PostgreSQL + pgvector en producción (DigitalOcean)
    """
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name='embedding')
    embedding_data = models.JSONField(blank=True, default=dict)
    model_name = models.CharField(max_length=100, default='sentence-transformers/all-MiniLM-L6-v2')
    document_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Embeddings: {self.module.name} ({self.document_count} docs)"
    
    class Meta:
        verbose_name = "Module Embedding"
        verbose_name_plural = "Module Embeddings"


class StudentProfile(models.Model):
    """
    Perfil de cada estudiante que ha iniciado sesión en Kairos.
    Se crea automáticamente en el primer login.
    
    Arquitectura: Un registro por estudiante. Compatible con
    PostgreSQL (Oracle/DigitalOcean), MySQL, SQLite.
    
    El canvas_user_id es el identificador UNIVERSAL del estudiante
    en Canvas LMS — es el mismo ID independientemente del curso.
    Se usa para cruzar datos con la API de Canvas (enrollments).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    canvas_user_id = models.IntegerField(unique=True, db_index=True)
    display_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default='')
    avatar_url = models.URLField(blank=True, null=True)
    
    # Login tracking
    first_login_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(default=timezone.now)
    total_logins = models.PositiveIntegerField(default=1)
    
    # Activity tracking (se actualiza desde otros módulos)
    total_questions_asked = models.PositiveIntegerField(default=0)
    total_modules_studied = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        indexes = [
            models.Index(fields=['canvas_user_id']),
            models.Index(fields=['last_login_at']),
        ]
    
    def __str__(self):
        return f"{self.display_name} (Canvas #{self.canvas_user_id})"
    
    def logins_this_week(self):
        """Cuenta logins de la semana actual (lunes a domingo)."""
        from datetime import timedelta
        now = timezone.now()
        # Inicio de la semana (lunes)
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return self.login_records.filter(timestamp__gte=week_start).count()


class LoginRecord(models.Model):
    """
    Registro individual de cada inicio de sesión en Kairos.
    
    Arquitectura para producción:
    - Index compuesto (student_profile, timestamp) para queries por rango de fecha O(log n)
    - Particionable por mes en PostgreSQL para deployments con millones de usuarios
    - Registros viejos pueden archivarse sin afectar queries recientes
    
    Se usa para:
    - Calcular "veces esta semana" (WHERE timestamp >= week_start)
    - Analítica de uso por profesor
    - Auditoría de acceso
    """
    student_profile = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name='login_records'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    
    class Meta:
        verbose_name = "Login Record"
        verbose_name_plural = "Login Records"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['student_profile', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.student_profile.display_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class ChatMessage(models.Model):
    """
    Modelo para almacenar conversaciones entre estudiantes e IA.
    """
    ROLE_CHOICES = [
        ('student', 'Estudiante'),
        ('ai', 'IA'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='chat_messages')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    # Tracking para debugging
    tokens_used = models.IntegerField(null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True)  # En segundos
    model_used = models.CharField(max_length=50, default='deepseek')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'course', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.role}: {self.content[:50]}"