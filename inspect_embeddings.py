#!/usr/bin/env python
"""
Inspeccionar el contenido de los embeddings para el módulo 2
"""

import os
import django
import json
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

print("=" * 80)
print("[INSPECCIÓN] Contenido de embeddings del módulo 2")
print("=" * 80)

embeddings_file = Path(".embeddings/module_2_course_1.json")

if not embeddings_file.exists():
    print("✗ Embeddings file not found")
    exit(1)

with open(embeddings_file) as f:
    data = json.load(f)

print(f"\n[ESTADÍSTICAS]")
print(f"Total documentos: {len(data.get('documents', []))}")
print(f"Total embeddings: {len(data.get('embeddings', []))}")
print(f"Total metadatos: {len(data.get('metadatas', []))}")

print(f"\n[DOCUMENTOS] (primeros 3)")
print("-" * 80)

for i, doc in enumerate(data.get('documents', [])[:3], 1):
    print(f"\n{i}. Longitud: {len(doc)} chars")
    print(f"   Preview:\n{doc[:200]}...\n")

# Verificar si hay contenido de PDF (buscar palabras clave)
all_text = " ".join(data.get('documents', []))
keywords = ['investigación', 'pdf', 'proyecto', 'contenido', 'página', 'capítulo']
found_keywords = [kw for kw in keywords if kw.lower() in all_text.lower()]

print(f"\n[ANÁLISIS DE CONTENIDO]")
if found_keywords:
    print(f"✅ Palabras clave encontradas: {', '.join(found_keywords)}")
else:
    print(f"⚠️ NO se encontraron palabras clave del contenido")

# Verificar si es solo nombres de archivo
if "Archivo" in all_text or "archivo" in all_text:
    embedding_count = sum(1 for d in data.get('documents', []) if len(d) < 100)
    if embedding_count > len(data.get('documents', [])) / 2:
        print(f"⚠️ PROBLEMA: Muchos embeddings son muy cortos (solo nombres)")
        print(f"   Esto significa que el contenido del PDF NO fue extraído correctamente")
    else:
        print(f"✅ Embeddings contienen contenido sustancial (no solo nombres)")

print("\n" + "=" * 80)
