#!/usr/bin/env python
"""
Resetear algunos módulos a estado 'not_analyzed' para testing
"""
import sys, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from tu_app.models import Module, ModuleAnalysis

print("\nRESETEANDO MODULOS...")
print("="*60)

# Resetear módulos 3, 4, 5 a 'not_analyzed'
modules_to_reset = [3, 4, 5]

for module_id in modules_to_reset:
    try:
        module = Module.objects.get(id=module_id)
        analysis = ModuleAnalysis.objects.get(module=module)
        
        # Cambiar estado a 'not_analyzed'
        analysis.status = 'not_analyzed'
        analysis.save()
        
        print(f"[OK] Module {module_id} ({module.name}) -> 'not_analyzed'")
    except Exception as e:
        print(f"[ERROR] Module {module_id}: {e}")

print("\nAhora véamos el estado:")
print("="*60)

for module in Module.objects.all()[:5]:
    try:
        analysis = ModuleAnalysis.objects.get(module=module)
        status = analysis.status
    except:
        status = 'NOT IN DB'
    
    print(f"Module {module.id} ({module.name}): {status}")

print("\nLos módulos 3, 4, 5 ahora deberian mostrar GRIS (Sin analizar)")
print("Los módulos 1, 2 deberian mostrar VERDE (Analizado)")
