#!/usr/bin/env python
"""
Buscar el PDF "Proyecto de investigación" en todos los módulos
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module, ModuleItem
from django.contrib.auth.models import User
import json
from pathlib import Path

print("=" * 80)
print("[BÚSQUEDA] Dónde está el PDF 'Proyecto de investigación'")
print("=" * 80)

user = User.objects.first()

# Buscar items con "proyecto" en el título
items_with_proyecto = ModuleItem.objects.filter(
    module__course__user=user,
    title__icontains='proyecto'
)

print(f"\n[RESULTADOS] Items con 'proyecto' en el título: {items_with_proyecto.count()}")
for item in items_with_proyecto:
    print(f"\n  📄 {item.title}")
    print(f"     Módulo: {item.module.name} (ID: {item.module.id})")
    print(f"     Tipo: {item.get_item_type_display()}")
    if item.url:
        print(f"     URL: {item.url[:80]}")
    
    # Verificar si hay embeddings JSON para este módulo
    embeddings_file = Path(f".embeddings/module_{item.module.id}_course_{item.module.course.id}.json")
    if embeddings_file.exists():
        with open(embeddings_file) as f:
            data = json.load(f)
            docs = data.get('documents', [])
            # Buscar si este item está en los embeddings
            matching_docs = [d for d in docs if 'proyecto' in d.lower() or item.title in d]
            if matching_docs:
                print(f"     ✅ Embeddings: ENCONTRADOS ({len(matching_docs)} coincidencias)")
                for doc in matching_docs[:1]:
                    print(f"        Preview: {doc[:100]}...")
            else:
                print(f"     ⚠️ Embeddings: {len(docs)} docs pero sin 'proyecto'")
    else:
        print(f"     ❌ Embeddings: NO EXISTEN")

print("\n" + "=" * 80)
