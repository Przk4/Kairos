#!/usr/bin/env python
"""Test the modified debug_stats endpoint"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from django.test import RequestFactory
from tu_app.views import debug_stats
import json

print("\n" + "=" * 80)
print("PROBANDO: debug_stats endpoint con datos de BD")
print("=" * 80 + "\n")

try:
    factory = RequestFactory()
    request = factory.get('/api/debug/stats/')
    response = debug_stats(request)
    
    data = json.loads(response.content.decode('utf-8'))
    
    print("Response Status:", response.status_code)
    print("\nRAG Stats from BD:")
    print(json.dumps(data['rag'], indent=2))
    
    print("\n" + "=" * 80)
    print("RESULTADO:")
    print("=" * 80)
    print(f"Total Embeddings (de BD): {data['rag']['total_embeddings']}")
    print(f"Modulos Analizados (de BD): {data['rag']['modules_analyzed']}")
    print(f"\n✅ Dashboard ahora mostrará estos números REALES de BD")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
