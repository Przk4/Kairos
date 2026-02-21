#!/usr/bin/env python
"""Diagnóstico de estado de módulos en BD"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import Module, ModuleAnalysis, ModuleEmbedding

print("=" * 80)
print("DIAGNOSTICO: MODULOS Y SU ESTADO EN BD")
print("=" * 80)

for module in Module.objects.all():
    # Obtener estado
    try:
        analysis = ModuleAnalysis.objects.get(module=module)
        db_status = analysis.status
    except ModuleAnalysis.DoesNotExist:
        db_status = 'not_analyzed'
    
    # Obtener embeddings
    try:
        embedding = ModuleEmbedding.objects.get(module=module)
        has_embeddings = embedding.embedding_data is not None and len(embedding.embedding_data) > 0
        doc_count = embedding.document_count if hasattr(embedding, 'document_count') else 0
    except ModuleEmbedding.DoesNotExist:
        has_embeddings = False
        doc_count = 0
    
    is_analyzed = (db_status == 'completed' and has_embeddings)
    
    print(f"\n[MODULE {module.id}] {module.name}")
    print(f"    analysis_status: '{db_status}'")
    print(f"    embeddings: {has_embeddings}")
    if has_embeddings:
        print(f"      document_count: {doc_count}")
    print(f"    >> is_analyzed: {is_analyzed}")
    
    # Mostrar qué botón debería mostrar
    if is_analyzed and db_status == 'completed':
        button_text = "[RE-ANALYZE]"
    elif db_status == 'analyzing':
        button_text = "[ANALYZING]"
    else:
        button_text = "[ANALYZE]"
    
    print(f"    button: {button_text}")
