#!/usr/bin/env python
"""
Test directo de la lógica del endpoint (sin Django test client)
"""
import sys, os, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from tu_app.models import Module, ModuleAnalysis

print("\nVERIFICANDO ESTADO DE CADA MODULO")
print("="*60)

for module_id in [1, 2, 3, 4, 5]:
    try:
        module = Module.objects.get(id=module_id)
        
        # Obtener estado BD
        try:
            analysis = ModuleAnalysis.objects.get(module=module)
            db_status = analysis.status
        except:
            db_status = 'not_analyzed'
        
        # Validar archivo de embeddings
        embeddings_file = f".embeddings/module_{module.id}_course_{module.course.id}.json"
        has_real_embeddings = False
        
        if os.path.exists(embeddings_file):
            try:
                with open(embeddings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    has_real_embeddings = len(data.get('documents', [])) > 0
            except:
                has_real_embeddings = False
        
        # Decisión final
        is_analyzed = (db_status == 'completed' and has_real_embeddings)
        
        status_text = "VERDE (analizado)" if is_analyzed else "GRIS (sin analizar)"
        
        print(f"Module {module_id} ({module.name}):")
        print(f"  BD Status: {db_status}")
        print(f"  Has File: {has_real_embeddings}")
        print(f"  Result: {status_text}")
        print()
        
    except Exception as e:
        print(f"ERROR Module {module_id}: {e}\n")

print("="*60)
