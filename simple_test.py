#!/usr/bin/env python
"""
Test simplificado de la lógica del endpoint
"""
import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.models import Module

print("\n" + "="*60)
print("ESTADO DE MODULOS")
print("="*60)

for mod in Module.objects.all()[:3]:
    print(f"\nModule {mod.id}: {mod.name}")
    
    # Lógica del endpoint
    try:
        from tu_app.models import ModuleAnalysis
        analysis = ModuleAnalysis.objects.get(module=mod)
        db_status = analysis.status
    except:
        db_status = 'not_analyzed'
    
    items_count = mod.items.count()
    
    print(f"  DB Status: {db_status}")
    print(f"  Items: {items_count}")
    print(f"  -> RESULTADO: {db_status}")
