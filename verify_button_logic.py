#!/usr/bin/env python
"""Verificar que la lógica de botones es correcta"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import Module, ModuleEmbedding

print("=" * 80)
print("VERIFICACION: LOGICA DE BOTONES (basada SOLO en vectores guardados)")
print("=" * 80)

for module in Module.objects.all():
    try:
        embedding = ModuleEmbedding.objects.get(module=module)
        docs = embedding.embedding_data.get('documents', []) if embedding.embedding_data else []
        doc_count = len(docs)
        db_doc_count = embedding.document_count
    except ModuleEmbedding.DoesNotExist:
        doc_count = 0
        db_doc_count = 0
    
    # is_analyzed SOLO depende de si hay vectores
    is_analyzed = doc_count > 0
    
    # Determinar qué botón mostrar
    if is_analyzed:
        button_text = "RE-ANALIZAR"
        status_text = "VECTORES GUARDADOS"
    else:
        button_text = "ANALIZAR"
        status_text = "SIN VECTORES"
    
    print(f"\n[MODULE {module.id}] {module.name}")
    print(f"    Documentos en embedding_data: {doc_count}")
    print(f"    document_count en BD: {db_doc_count}")
    print(f"    is_analyzed: {is_analyzed}")
    print(f"    Estado: {status_text}")
    print(f"    Boton: {button_text}")

print("\n" + "=" * 80)
print("Si todos muestran doc_count=0, los botones seran ANALIZAR para todos")
print("=" * 80)
