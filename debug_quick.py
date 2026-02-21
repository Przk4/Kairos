#!/usr/bin/env python
"""
Script RÁPIDO para debuggear estado sin cargar transformers
"""
import os
import sys
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.models import Module, ModuleAnalysis

print("\n" + "="*80)
print("ESTADO DE MÓDULOS EN BD")
print("="*80)

modules = Module.objects.all()[:10]

for module in modules:
    print(f"\n📦 Módulo {module.id}: {module.name}")
    
    # Estado en BD
    try:
        analysis = ModuleAnalysis.objects.get(module=module)
        db_status = analysis.status
        print(f"   DB Status: {db_status}")
        print(f"   Created: {analysis.created_at}")
        print(f"   Updated: {analysis.updated_at}")
    except ModuleAnalysis.DoesNotExist:
        print(f"   DB Status: NO EXISTS")
    
    # Items
    items_count = module.items.count()
    print(f"   Items: {items_count}")

print("\n" + "="*80)
