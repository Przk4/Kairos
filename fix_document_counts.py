#!/usr/bin/env python
"""Corregir document_count en ModuleEmbedding para todos los módulos"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import ModuleEmbedding, Module

print("\n" + "=" * 80)
print("CORRECCIÓN: Actualizar document_count en ModuleEmbedding")
print("=" * 80)

updated = 0
for module in Module.objects.all():
    try:
        embedding = ModuleEmbedding.objects.get(module=module)
        
        # Obtener cuenta correcta de documentos
        docs = embedding.embedding_data.get('documents', []) if embedding.embedding_data else []
        correct_count = len(docs)
        current_count = embedding.document_count
        
        if current_count != correct_count:
            embedding.document_count = correct_count
            embedding.save()
            print(f"[UPDATED] Módulo {module.id}: {current_count} -> {correct_count}")
            updated += 1
        else:
            print(f"[OK] Módulo {module.id}: {correct_count} (ya correcto)")
            
    except ModuleEmbedding.DoesNotExist:
        print(f"[SKIP] Módulo {module.id}: NO ModuleEmbedding")

print(f"\nTotal actualizado: {updated}")
print("=" * 80)
