#!/usr/bin/env python
"""
Test completo del flujo: obtener módulo, sincronizar items, y analizar con Token
"""

import os
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module, ModuleItem
from tu_app.rag_service import get_rag_service
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

print("=" * 80)
print("[TEST] Flujo completo: Sincronizar items y analizar módulo")
print("=" * 80)

try:
    # Obtener primer usuario
    user = User.objects.first()
    if not user:
        print("✗ No user found")
        exit(1)
    
    print(f"\n[USUARIO] {user.username}")
    
    # Obtener Canvas token
    from tu_app.views import get_valid_canvas_token
    access_token = get_valid_canvas_token(user)
    if not access_token:
        print("✗ No Canvas token available")
        exit(1)
    
    print(f"✓ Canvas token obtained: {access_token[:20]}...")
    
    # Obtener un módulo para análisis
    module = Module.objects.filter(course__user=user).first()
    if not module:
        print("✗ No module found")
        exit(1)
    
    print(f"\n[MÓDULO] {module.name} (ID: {module.id})")
    
    # Ver items actuales
    items = module.items.all()
    print(f"[ITEMS] Total items en DB: {items.count()}")
    
    # Mostrar URLs de los items
    print("\n[VERIFICAR URLs en items]")
    for i, item in enumerate(items[:3], 1):
        print(f"  {i}. {item.title}")
        print(f"     URL: {item.url[:80]}...")
        print(f"     Type: {item.get_item_type_display()}")
    
    # Obtener RAG service
    rag_service = get_rag_service()
    print(f"\n[RAG SERVICE] Backend: {'ChromaDB' if rag_service.using_chromadb else 'In-Memory'}")
    
    # Ejecutar análisis
    print(f"\n[ANÁLISIS] Iniciando análisis del módulo...")
    print("-" * 80)
    
    success = rag_service.analyze_module(module, access_token)
    
    print("-" * 80)
    
    if success:
        print(f"\n✓ Análisis completado exitosamente")
        
        # Verificar embeddings
        collection_name = f"module_{module.id}_course_{module.course.id}"
        embeddings_count = rag_service.get_embeddings_count(collection_name)
        print(f"[EMBEDDINGS] Total embeddings creados: {embeddings_count}")
        
        if embeddings_count > 0:
            print(f"✓ ¡¡¡ÉXITO!!! Embeddings fueron creados correctamente")
        else:
            print(f"⚠ WARNING: No embeddings were created")
    else:
        print(f"\n✗ Analysis failed")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
