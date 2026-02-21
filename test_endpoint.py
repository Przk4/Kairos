#!/usr/bin/env python
"""
Test directo del endpoint sin cargar Django models pesados
"""
import os
import sys
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from tu_app.models import Course, Module

print("\n" + "="*80)
print("TEST DEL ENDPOINT /api/module/{id}/analysis-status/")
print("="*80)

# Crear cliente HTTP
client = Client()

# Obtener algunos módulos
modules = Module.objects.all()[:3]

for module in modules:
    print(f"\n[MODULE {module.id}] Testing...")
    
    # Llamar endpoint
    url = f'/api/module/{module.id}/analysis-status/'
    print(f"   URL: {url}")
    
    response = client.get(url)
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Response:")
        for key, value in data.items():
            print(f"      {key}: {value}")
    else:
        print(f"   ERROR: {response.content.decode()}")

print("\n" + "="*80)
