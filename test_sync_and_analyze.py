#!/usr/bin/env python
"""
Test completo: 1) Sincronizar items, 2) Analizar módulo
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module
from tu_app.rag_service import get_rag_service
from tu_app.canvas_auth import sync_module_items
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

print("=" * 80)
print("[TEST] Sincronizar items + Analizar módulo")
print("=" * 80)

try:
    # Obtener usuario y token
    user = User.objects.first()
    if not user:
        print("✗ No user found")
        exit(1)
    
    from tu_app.views import get_valid_canvas_token
    access_token = get_valid_canvas_token(user)
    if not access_token:
        print("✗ No Canvas token available")
        exit(1)
    
    print(f"\n[USUARIO] {user.username}")
    print(f"[TOKEN] {access_token[:20]}...")
    
    # Obtener módulo
    module = Module.objects.filter(course__user=user).first()
    if not module:
        print("✗ No module found")
        exit(1)
    
    print(f"\n[MÓDULO] {module.name} (ID: {module.id})")
    
    # PASO 1: SINCRONIZAR ITEMS
    print(f"\n[PASO 1] Sincronizando items del módulo...")
    print("-" * 80)
    
    headers = {'Authorization': f'Bearer {access_token}'}
    sync_module_items(user, module, headers)
    
    # Verificar items después de sincronización
    items = module.items.all()
    print(f"✓ Items sincronizados: {items.count()}")
    
    for i, item in enumerate(items[:3], 1):
        print(f"  {i}. {item.title}")
        print(f"     Type: {item.get_item_type_display()}")
        if item.url:
            print(f"     URL: {item.url[:60]}...")
    
    if items.count() == 0:
        print("⚠ No items to analyze")
        exit(1)
    
    # PASO 2: ANALIZAR
    print(f"\n[PASO 2] Analizando módulo...")
    print("-" * 80)
    
    rag_service = get_rag_service()
    success = rag_service.analyze_module(module, access_token)
    
    print("-" * 80)
    
    if success:
        print(f"\n✓ Análisis completado exitosamente")
        
        # Verificar embeddings
        collection_name = f"module_{module.id}_course_{module.course.id}"
        embeddings_count = rag_service.get_embeddings_count(collection_name)
        print(f"[EMBEDDINGS] Total: {embeddings_count}")
        
        if embeddings_count > 0:
            print(f"✓ ¡¡¡ÉXITO!!! Embeddings creados y con contenido de PDFs")
        else:
            print(f"⚠ WARNING: No embeddings created")
    else:
        print(f"\n✗ Analysis failed")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
