#!/usr/bin/env python
"""Debug: Verificar qué devuelve get_all_modules_stats"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from django.test import RequestFactory
from tu_app.views import get_all_modules_stats
import json

print("\n" + "=" * 80)
print("VERIFICANDO: /api/modules/stats-all/")
print("=" * 80 + "\n")

try:
    factory = RequestFactory()
    request = factory.get('/api/modules/stats-all/')
    response = get_all_modules_stats(request)
    
    data = json.loads(response.content.decode('utf-8'))
    
    print("Respuesta del endpoint:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 80)
    print("VALORES KEY:")
    print("=" * 80)
    print(f"status: {data.get('status')}")
    print(f"total_modules: {data.get('total_modules')}")
    print(f"total_embeddings: {data.get('total_embeddings')}")
    print(f"timestamp: {data.get('timestamp')}")
    
    if 'modules' in data:
        print(f"\nModulos ({len(data['modules'])} total):")
        for mod in data['modules']:
            print(f"  [{mod['id']}] {mod['name']}: {mod['embeddings_count']} docs")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
