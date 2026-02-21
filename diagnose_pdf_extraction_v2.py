#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para diagnosticar por qué los PDFs no se están extrayendo.
Version 2 - Encuentra automáticamente el usuario con cursos
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.models import Course, Module, ModuleItem, CanvasToken
from tu_app.rag_service import get_rag_service
from tu_app.canvas_auth import get_valid_canvas_token
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("DIAGNOSTICO v2: PDF EXTRACTION")
print("="*80)

try:
    # 1. Listar usuarios con tokens
    print("\n[STEP 1] Listando usuarios con Canvas tokens...")
    tokens = CanvasToken.objects.all()
    if not tokens:
        print("  [WARN] No Canvas tokens found in database")
        sys.exit(0)
    
    for token in tokens:
        print(f"  - User: {token.user.username} (Token expires: {token.expires_at})")
    
    # 2. Encontrar usuario con cursos
    print("\n[STEP 2] Buscando usuario con cursos...")
    user = None
    courses = None
    
    for token in tokens:
        user = token.user
        courses = Course.objects.filter(user=user)
        if courses.exists():
            print(f"  [OK] Found {len(courses)} courses for user: {user.username}")
            break
    
    if not courses or not courses.exists():
        print("  [WARN] No courses found for any user")
        sys.exit(0)
    
    # 3. Procesar primer curso
    course = courses.first()
    modules = course.modules.all()
    print(f"\n[STEP 3] Curso: {course.name}")
    print(f"  - Módulos: {len(modules)}")
    
    if not modules:
        print("  [WARN] No modules found")
        sys.exit(0)
    
    # 4. Procesar módulos y items
    rag_service = get_rag_service()
    access_token = get_valid_canvas_token(user)  # Returns string or None
    
    print(f"\n[STEP 4] Intentando extraer PDFs...")
    print(f"  - Usuario: {user.username}")
    print(f"  - Token disponible: {bool(access_token)}")
    
    items_processed = 0
    items_with_ext_success = 0
    items_with_ext_fail = 0
    
    for module in list(modules)[:2]:  # First 2 modules
        items = module.items.all()  # Correct relationship name: items, not module_items
        if not items:
            continue
        
        print(f"\n  [MODULE] {module.name} (ID: {module.id})")
        print(f"    - Items total: {len(items)}")
        
        for item in list(items)[:2]:  # First 2 items per module
            items_processed += 1
            print(f"\n    [ITEM] {item.title}")
            print(f"      - Type: {item.get_item_type_display()}")
            print(f"      - URL: {item.url[:80] if item.url else 'None'}...")
            
            if item.url:
                try:
                    # Intentar extraer
                    extracted = rag_service._extract_text_from_file(item.url, access_token)
                    
                    if extracted:
                        items_with_ext_success += 1
                        print(f"      [OK] Extraction SUCCESS - {len(extracted)} chars")
                        print(f"          Preview: {extracted[:100]}...")
                    else:
                        items_with_ext_fail += 1
                        print(f"      [FAIL] Extraction FAILED (returned None)")
                except Exception as e:
                    items_with_ext_fail += 1
                    print(f"      [ERROR] Extraction ERROR: {str(e)[:100]}")
    
    # Resumen
    print(f"\n" + "="*80)
    print(f"RESUMEN")
    print(f"="*80)
    print(f"Items procesados: {items_processed}")
    print(f"Extracciones exitosas: {items_with_ext_success}")
    print(f"Extracciones fallidas: {items_with_ext_fail}")
    
    if items_with_ext_success == 0:
        print("\n[CRITICAL] No PDFs se extrajeron exitosamente!")
        print("  → El problema está en la función _extract_text_from_file()")
        print("  → Posible causa: CANVAS_API_URL incorrecto o Token expirado")
    elif items_with_ext_success > 0:
        print(f"\n[OK] {items_with_ext_success} PDFs extraídos exitosamente")

except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    import traceback
    print(f"\n[ERROR] {e}")
    traceback.print_exc()

print("\n" + "="*80)
