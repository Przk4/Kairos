#!/usr/bin/env python
"""Debug simple: Llamar la función directamente sin test client"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import Module, ModuleEmbedding
from django.utils import timezone
import json

print("\n" + "=" * 80)
print("VERIFICANDO: Direct logic de get_all_modules_stats")
print("=" * 80 + "\n")

try:
    modules = Module.objects.all()
    total_embeddings = 0
    modules_data = []
    
    print(f"Total modulos en BD: {modules.count()}\n")
    
    for module in modules:
        try:
            embedding = ModuleEmbedding.objects.get(module=module)
            docs = embedding.embedding_data.get('documents', []) if embedding.embedding_data else []
            doc_count = len(docs)
            print(f"[OK] Module {module.id}: {doc_count} docs")
        except ModuleEmbedding.DoesNotExist:
            doc_count = 0
            print(f"[NO] Module {module.id}: NO ModuleEmbedding")
        
        total_embeddings += doc_count
        
        has_embeddings = doc_count > 0
        button_text = 'RE-ANALIZAR' if has_embeddings else 'ANALIZAR'
        
        modules_data.append({
            'id': module.id,
            'name': module.name,
            'embeddings_count': doc_count,
            'has_embeddings': has_embeddings,
            'button_text': button_text
        })
    
    result = {
        'status': 'ok',
        'timestamp': str(timezone.now()),
        'total_modules': modules.count(),
        'total_embeddings': total_embeddings,
        'modules': modules_data
    }
    
    print("\n" + "=" * 80)
    print("RESULTADO:")
    print("=" * 80 + "\n")
    
    print(f"Total embeddings GUARDADOS: {result['total_embeddings']}")
    print(f"Total modulos: {result['total_modules']}")
    
    print("\nJSON Response:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
