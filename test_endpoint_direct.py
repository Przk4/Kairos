#!/usr/bin/env python
"""Simple test del nuevo endpoint - sin Django test client"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import Module, ModuleEmbedding
from tu_app.views import get_all_modules_stats
from django.test import RequestFactory
import json

print("\n" + "=" * 80)
print("PROBANDO: get_all_modules_stats (direct call)")
print("=" * 80 + "\n")

try:
    # Llamar la función directamente
    factory = RequestFactory()
    request = factory.get('/api/modules/stats-all/')
    response = get_all_modules_stats(request)
    
    # Parsear respuesta
    data = json.loads(response.content.decode('utf-8'))
    
    print(f"[OK] Respuesta recibida")
    print(f"\nJSON:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    print(f"\n" + "=" * 80)
    print(f"RESUMEN:")
    print(f"=" * 80)
    print(f"Total modulos: {data['total_modules']}")
    print(f"Total embeddings: {data['total_embeddings']}")
    print(f"\nDetalle por modulo:")
    
    for mod in data['modules']:
        status = "TIENE VECTORES" if mod['has_embeddings'] else "VACIO"
        print(f"  [{mod['id']}] {mod['name']:20} | {mod['embeddings_count']:3} docs | {status:20} | {mod['button_text']}")
    
    print("\n" + "=" * 80)
    
except Exception as e:
    print(f"[ERROR] Excepcion: {e}")
    import traceback
    traceback.print_exc()
