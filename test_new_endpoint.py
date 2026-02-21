#!/usr/bin/env python
"""Probar el nuevo endpoint get_all_modules_stats"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from django.test import Client
import json

client = Client()

print("\n" + "=" * 80)
print("PROBANDO: /api/modules/stats-all/")
print("=" * 80 + "\n")

try:
    response = client.get('/api/modules/stats-all/')
    data = response.json()
    
    if response.status_code == 200:
        print(f"[OK] Endpoint respondio con 200")
        print(f"\nRespuesta JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        print(f"\n" + "=" * 80)
        print(f"RESUMEN:")
        print(f"=" * 80)
        print(f"Total modulos: {data['total_modules']}")
        print(f"Total embeddings: {data['total_embeddings']}")
        print(f"\nDetalle por modulo:")
        
        for mod in data['modules']:
            print(f"  [{mod['id']}] {mod['name']}")
            print(f"      Embeddings: {mod['embeddings_count']}")
            print(f"      Boton: {mod['button_text']}")
    else:
        print(f"[ERROR] Codigo: {response.status_code}")
        print(f"Respuesta: {data}")
        
except Exception as e:
    print(f"[ERROR] Excepcion: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
