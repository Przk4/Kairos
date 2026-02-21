#!/usr/bin/env python
"""
Test que el endpoint devuelve los estados correctos
"""
import sys, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from django.test import Client

print("\nTESTEANDO ENDPOINT /api/module/{id}/analysis-status/")
print("="*60)

client = Client()

for module_id in [1, 2, 3, 4, 5]:
    response = client.get(f'/api/module/{module_id}/analysis-status/')
    
    if response.status_code == 200:
        data = response.json()
        status = "VERDE (analizado)" if data['is_analyzed'] else "GRIS (sin analizar)"
        print(f"Module {module_id}: {status}")
        print(f"  -> {data['analysis_status']}")
    else:
        print(f"Module {module_id}: ERROR {response.status_code}")

print("\n" + "="*60)
