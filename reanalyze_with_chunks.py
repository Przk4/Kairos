#!/usr/bin/env python
"""
Re-analizar módulo 2 con nuevo código de chunking y limpieza
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module
from tu_app.rag_service import get_rag_service
from tu_app.views import get_valid_canvas_token
from django.contrib.auth.models import User

print("[1] Getting user...")
user = User.objects.first()
if not user:
    print("[ERROR] No user")
    exit(1)

print("[2] Getting Canvas token...")
access_token = get_valid_canvas_token(user)
if not access_token:
    print("[ERROR] No Canvas token")
    exit(1)

print("[3] Getting module 2...")
module = Module.objects.filter(id=2, course__user=user).first()
if not module:
    print("[ERROR] Module 2 not found")
    exit(1)

print(f"[4] Re-analyzing {module.name}...")
rag_service = get_rag_service()
success = rag_service.analyze_module(module, access_token)

if success:
    print(f"[OK] Module {module.id} analyzed successfully")
else:
    print(f"[ERROR] Analysis failed")
