# Sistema de Diferenciación de Usuarios y Módulos

## 🎯 ¿Qué se implementó?

### 1. **Diferenciación de Cuentas**
- Campo `role` en `CanvasToken` con opciones: `student`, `teacher`, `admin`, `unknown`
- Función `detect_user_role()` que analiza automáticamente las inscripciones en Canvas
- Al login, se detecta automáticamente si es estudiante o maestro

**¿Cómo funciona la detección?**
```
Canvas API → Obtiene cursos con enrollments → Verifica tipos:
- 'TeacherEnrollment' → Rol: MAESTRO
- 'StudentEnrollment' → Rol: ESTUDIANTE
- Ambos → Prioriza: MAESTRO
```

### 2. **Modelos de Base de Datos**

#### `Course` (Cursos)
```python
- user: Django User
- canvas_course_id: ID único de Canvas
- name: Nombre del curso
- code: Código del curso
- enrollment_role: Tu rol en este curso
```

#### `Module` (Módulos)
```python
- course: Referencia al curso
- canvas_module_id: ID único de Canvas
- name: Nombre del módulo
- position: Orden
- is_locked: Si está bloqueado
```

#### `ModuleItem` (Materiales dentro de módulos)
```python
- module: Referencia al módulo
- canvas_item_id: ID único
- title: Título del material
- item_type: Tipo (File, Page, Assignment, Quiz, Discussion, etc.)
- position: Orden
- url: Link si aplica
- is_locked: Si está bloqueado
- completion_requirement: Requisito de completación
```

### 3. **Funciones de Sincronización**

#### `sync_courses_for_user(user)`
Obtiene TODOS los cursos del usuario desde Canvas y los almacena en BD.
```python
Canvas → GET /api/v1/courses → BD (tabla Course)
```

#### `sync_modules_for_course(user, course)`
Obtiene TODOS los módulos de un curso específico.
```python
Canvas → GET /api/v1/courses/{id}/modules → BD (tabla Module)
```

#### `sync_module_items(user, module, headers)`
Obtiene todos los items (materiales) de cada módulo.
```python
Canvas → GET /api/v1/courses/{course_id}/modules/{module_id}/items → BD (tabla ModuleItem)
```

### 4. **Flujo de Autenticación Mejorado**

```
1. Usuario hace login con Canvas
   ↓
2. Se crea/actualiza CanvasToken con role='unknown'
   ↓
3. Se detecta automáticamente el rol (student/teacher)
   ↓
4. Si es ESTUDIANTE:
   - Se sincronizan sus cursos
   - Se sincronizan los módulos de cada curso
   - Se sincronizan todos los materiales
   ↓
5. Dashboard muestra información según el rol
```

## 💾 Estructura de la BD

```
User (Django)
  ↓
  └─ CanvasToken (1:1)
      - role: 'student' / 'teacher'
      - access_token
      - canvas_user_id
      ↓
      └─ Course (1:Many)
          - canvas_course_id
          - name, code
          ↓
          └─ Module (1:Many)
              - canvas_module_id
              - position
              ↓
              └─ ModuleItem (1:Many)
                  - item_type: File, Assignment, etc.
                  - position
                  - content_id
```

## 🔍 ¿Cómo usar en templates?

```html
{% if is_student %}
  <!-- Dashboard para estudiantes -->
  {% for course in courses %}
    <h2>{{ course.name }}</h2>
    {% for module in course.modules.all %}
      <h3>{{ module.name }}</h3>
      {% for item in module.items.all %}
        <p>{{ item.title }} ({{ item.get_item_type_display }})</p>
      {% endfor %}
    {% endfor %}
  {% endfor %}

{% elif is_teacher %}
  <!-- Dashboard para maestros -->
  <p>Viendo como Maestro</p>
{% endif %}
```

## 🚀 Próximos Pasos Sugeridos

1. **Crear templates** para mostrar cursos/módulos/materiales
2. **Dashboard para maestros** - opciones de crear contenido
3. **Tutor IA** - Analizar respuestas de estudiantes con IA
4. **Reformulación de tareas** - Cambiar enunciados para evitar copia directa
5. **Tracking de progreso** - Ver qué ha visto el estudiante

## 📝 Administración

Para ver los datos en Django Admin:
```
python manage.py createsuperuser
# Visita http://localhost:8000/admin/
```

Luego registra en `admin.py`:
```python
admin.site.register(Course)
admin.site.register(Module)
admin.site.register(ModuleItem)
```

---

**¿Listo para el siguiente paso?** 🎓
