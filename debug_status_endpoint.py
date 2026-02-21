#!/usr/bin/env python
"""
Script para debuggear qué devuelve el endpoint de estado
"""
import os
import sys
import django
import json

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
django.setup()

from tu_app.models import Module, ModuleAnalysis
from tu_app.rag_service import get_rag_service
from tu_app.debug_service import get_debug_service

print("\n" + "="*80)
print("DEBUGGEAR ESTADO DE MÓDULOS")
print("="*80)

# Obtener todos los módulos
modules = Module.objects.all()[:5]

rag_service = get_rag_service()
debug_service = get_debug_service()

for module in modules:
    print(f"\n📦 Módulo: {module.id} - {module.name}")
    print(f"   Curso: {module.course.name}")
    
    # 1. Estado en BD
    try:
        analysis = ModuleAnalysis.objects.get(module=module)
        db_status = analysis.status
    except ModuleAnalysis.DoesNotExist:
        analysis = None
        db_status = 'not_analyzed'
    
    print(f"   DB Status: {db_status}")
    
    # 2. Documentos en debug service
    analyzed_docs = debug_service.get_analyzed_documents(module.id)
    document_count = len(analyzed_docs.get('documents', []))
    print(f"   Documentos (debug): {document_count}")
    
    # 3. Embeddings en RAG service
    collection_name = f"module_{module.id}_course_{module.course.id}"
    embeddings_count = rag_service.get_embeddings_count(collection_name)
    print(f"   Embeddings (RAG): {embeddings_count}")
    print(f"   Colección: {collection_name}")
    
    # 4. Items del módulo
    items_count = module.items.count()
    print(f"   Items totales: {items_count}")
    
    # 5. Lógica de decisión (igual al endpoint)
    has_embeddings = embeddings_count > 0
    
    if db_status == 'completed':
        is_analyzed = True
        reason = "DB Status = completed"
    elif has_embeddings:
        is_analyzed = True
        reason = "Has embeddings"
    else:
        is_analyzed = document_count > 0
        reason = "Has documents"
    
    print(f"   ✅ is_analyzed: {is_analyzed} ({reason})")
    
    # 6. Simular respuesta del endpoint
    response = {
        'is_analyzed': is_analyzed,
        'document_count': document_count,
        'embeddings_count': embeddings_count,
        'items_count': items_count,
        'analysis_status': db_status,
        'has_embeddings': has_embeddings,
    }
    
    print(f"   📊 Respuesta endpoint:")
    print(f"      {json.dumps(response, indent=6)}")

print("\n" + "="*80)
print("Fin del diagnóstico")
print("="*80)
