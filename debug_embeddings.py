#!/usr/bin/env python
"""
Debuggear qué archivos de embeddings existen y qué contienen
"""
import os
import json
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import Module, ModuleAnalysis

print("\n" + "="*80)
print("ANALISIS DE EMBEDDINGS Y ESTADO BD")
print("="*80)

for module in Module.objects.all()[:5]:
    print(f"\n[MODULE {module.id}] {module.name}")
    print(f"  Course: {module.course.id}")
    
    # Estado en BD
    try:
        analysis = ModuleAnalysis.objects.get(module=module)
        db_status = analysis.status
    except:
        db_status = 'NOT IN DB'
    
    print(f"  BD Status: {db_status}")
    
    # Buscar archivo de embeddings
    embeddings_file = f".embeddings/module_{module.id}_course_{module.course.id}.json"
    file_exists = os.path.exists(embeddings_file)
    
    if file_exists:
        try:
            with open(embeddings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                doc_count = len(data.get('documents', []))
                print(f"  File: EXISTS with {doc_count} documents")
        except Exception as e:
            print(f"  File: EXISTS but ERROR reading: {e}")
    else:
        print(f"  File: NOT EXISTS")

print("\n" + "="*80)
