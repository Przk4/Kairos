#!/usr/bin/env python
"""
Verificar que la tabla ModuleEmbedding existe
"""
import sys, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from tu_app.models import ModuleEmbedding, Module

print("Checking ModuleEmbedding table...")
try:
    count = ModuleEmbedding.objects.count()
    print(f"OK! ModuleEmbedding table exists. Current records: {count}")
except Exception as e:
    print(f"ERROR: {e}")
    print("Table doesn't exist - run: manage.py migrate")
