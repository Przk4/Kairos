# 🚀 GUIA DE DEPLOYMENT: KAIROS EN DIGITALOCEAN

## 1. PRE-REQUISITOS
- ✅ Embeddings migrados a BD (ModuleEmbedding) 
- ✅ Código listo y testeado localmente
- ✅ Git repository configurado
- ✅ DigitalOcean account

---

## 2. CREAR DATABASE EN DIGITALOCEAN

### 2.1 PostgreSQL Database
```
DigitalOcean → Manage → Databases → Create Database
- Engine: PostgreSQL 15+
- Region: Mismo que tu App Platform
- Size: Basic (1GB RAM, $15/mes)
- Backups: Habilitados

Guarda:
- Host: xxxx.ondigitalocean.com
- Port: 25060
- Database: kairos_prod
- Username: dbuser
- Password: [GENERAR FUERTE]
```

---

## 3. DEPLOYAR APP EN APP PLATFORM

### 3.1 Conectar GitHub
```
DigitalOcean → App Platform → Create App → Connect GitHub
- Repo: tu-repo/kairos
- Branch: main
- Auto-deploy: YES
```

### 3.2 Configurar Environment Variables
En App Platform → Edit → Runtime Settings:

```
ALLOWED_HOSTS=tu-app.ondigitalocean.app,www.tu-app.ondigitalocean.app
DEBUG=False
SECRET_KEY=<GENERAR: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'>

# Database PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=kairos_prod
DB_USER=dbuser
DB_PASSWORD=<PASSWORD de arriba>
DB_HOST=<HOST de arriba>
DB_PORT=25060

# Canvas OAuth
CANVAS_BASE_URL=https://tu-canvas-instance.com
CANVAS_CLIENT_ID=<TU_ID>
CANVAS_CLIENT_SECRET=<TU_SECRET>
CANVAS_REDIRECT_URI=https://tu-app.ondigitalocean.app/callback

# DeepSeek API
DEEPSEEK_API_KEY=<TU_KEY>

# Google Embeddings (si usas)
GOOGLE_APPLICATION_CREDENTIALS=/workspace/secrets/credentials.json
```

### 3.3 Configurar archivo `settings.py`

Reemplazar sección de BD:
```python
# En kairos_project/settings.py

import os

# Base de datos - PostgreSQL en DigitalOcean
if os.getenv('DB_ENGINE'):  # En producción
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE'),
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
        }
    }
else:  # Local (SQLite)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ALLOWED_HOSTS
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1').split(',')

# DEBUG
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# SECRET_KEY
SECRET_KEY = os.getenv('SECRET_KEY')
```

### 3.4 Dockerfile (Si App Platform lo pide)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Ejecutar migraciones
RUN python manage.py migrate --noinput
RUN python manage.py collectstatic --noinput

# Gunicorn server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "kairos_project.wsgi:application"]
```

---

## 4. MIGRACIONES EN CLOUD

### 4.1 Ejecutar migraciones después del primer deploy

```bash
# Via DigitalOcean Console
python manage.py migrate  # Crea todas las tablas
python manage.py createsuperuser  # Crear admin

# Via SSH
doctl apps logs --app-name=kairos --log-type=build
```

---

## 5. STATIC FILES EN CLOUD

### 5.1 Usando DigitalOcean Spaces (S3-compatible)

```python
# settings.py
import os
from storages.backends.s3boto3 import S3Boto3Storage

if not DEBUG:  # En producción
    AWS_ACCESS_KEY_ID = os.getenv('SPACES_ACCESS_KEY')
    AWS_SECRET_ACCESS_KEY = os.getenv('SPACES_SECRET_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('SPACES_BUCKET')
    AWS_S3_ENDPOINT_URL = 'https://nyc3.digitaloceanspaces.com'
    AWS_S3_REGION_NAME = 'nyc3'
    
    STATIC_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.nyc3.digitaloceanspaces.com/static/'
    STATIC_ROOT = 'static/'
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

Crear Spaces:
```
DigitalOcean → Spaces → Create → kairos-static
Generar Personal Access Token (para env vars)
```

---

## 6. VERIFICAR DEPLOYMENT

### 6.1 Checklist

- [ ] Base de datos PostgreSQL creada y conectada
- [ ] Environment variables configuradas
- [ ] ✅ Migraciones ejecutadas (ModuleEmbedding table existe)
- [ ] Static files servidos (CSS, JS cargando)
- [ ] Canvas OAuth funcionando
- [ ] DeepSeek API key validada
- [ ] Logs sin errores (DigitalOcean Console)

### 6.2 Comandos de debug

```bash
# Ver logs
doctl apps logs --app-name=kairos

# SSH a la app
doctl apps create-exec -a kairos

# Dentro del container
python manage.py shell
>>> from tu_app.models import ModuleEmbedding
>>> ModuleEmbedding.objects.count()  # Debería ser 6
```

---

## 7. CONFIGURACION POST-DEPLOYMENT

### 7.1 Backups automáticos
```
DigitalOcean → Databases → Select DB → Settings
- Automated backups: Enabled
- Backup window: Daily 00:00 UTC
- Retention: 7 days
```

### 7.2 Monitoring
```
DigitalOcean → Insights → Create Alert
- Database CPU > 80%
- Database Disk > 85%
- App Platform uptime
```

---

## 8. COSTOS ESTIMADOS (DigitalOcean)

| Recurso | Precio | Notas |
|---------|--------|-------|
| PostgreSQL 1GB | $15/mes | Enough para módulos |
| App Platform (starter) | $12/mes | Auto-scale available |
| Spaces 250GB | $5/mes | Static files + backups |
| **TOTAL** | **$32/mes** | Mucho mejor que alternatives |

---

## 9. MIGRACION DE DATOS EXISTENTES

### 9.1 Backup local y restore

```bash
# Export desde SQLite local
python manage.py dumpdata > backup.json

# Restore en PostgreSQL en cloud (opcional)
python manage.py loaddata backup.json
```

Pero recomendamos:
1. Dejar los embeddings que ya migraste a ModuleEmbedding
2. Usuarios/cursos se syncan automaticamente desde Canvas

---

## 10. FINAL CHECKLIST

- [ ] Repo en GitHub con `.gitignore` (no subir .env)
- [ ] `requirements.txt` actualizado: `pip freeze > requirements.txt`
- [ ] `.env.example` creado (sin secrets)
- [ ] PostgreSQL creado en DigitalOcean
- [ ] App Platform linkeado a GitHub
- [ ] Environment variables configuradas
- [ ] Deploy exitoso (verde en DigitalOcean)
- [ ] Migraciones ejecutadas (`manage.py migrate`)
- [ ] Superuser creado (`manage.py createsuperuser`)
- [ ] Acceder a https://tu-app.ondigitalocean.app
- [ ] (Opcional) Custom domain: Apuntar DNS a DigitalOcean

---

## 🎉 LISTO!

Tu Kairos está en la nube. Embeddings en PostgreSQL. Código auto-deploya con push a GitHub.

¿Preguntas? Revisar logs en DigitalOcean Console.
