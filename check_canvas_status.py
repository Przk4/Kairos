#!/usr/bin/env python
"""
Verificar estado de Canvas token - sin hacer nada más
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

print("[1] Django iniciado")

from tu_app.views import get_valid_canvas_token
from django.contrib.auth.models import User

print("[2] Buscando usuario...")

user = User.objects.first()
if not user:
    print("ERROR: No user found")
    exit(1)

print(f"[3] Usuario encontrado: {user.username}")

print("[4] Intentando obtener Canvas token...")
access_token = get_valid_canvas_token(user)

if not access_token:
    print("[5] ❌ CANVAS NO ESTÁ DISPONIBLE")
    print("\nEl token expiró o Canvas no está conectado.")
    print("Esperando a que Canvas se reconecte...")
else:
    print(f"[5] ✅ CANVAS DISPONIBLE")
    print(f"    Token: {access_token[:30]}...")
