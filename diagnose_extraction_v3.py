#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script v3 para diagnosticar extraccion de PDFs
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

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("DIAGNÓSTICO v3: EXTRACCIÓN DE ARCHIVOS")
print("="*80)

try:
    # 1. Listar usuarios con tokens
    print("\n[1/4] Listando usuarios con Canvas tokens...")
    tokens = CanvasToken.objects.all()
    if not tokens:
        print("  [WARN] No Canvas tokens found")
        sys.exit(0)
    
    users_with_tokens = [token.user for token in tokens]
    print(f"  Found {len(users_with_tokens)} users with Canvas tokens")
    
    # 2. Encontrar usuario con cursos
    print("\n[2/4] Buscando usuario con cursos...")
    course = None
    user = None
    
    for u in users_with_tokens:
        c = Course.objects.filter(user=u).first()
        if c:
            user = u
            course = c
            break
    
    if not course:
        print("  [WARN] Nobody has courses")
        sys.exit(0)
    
    print(f"  Found course: {course.name}")
    
    # 3. Obtener token
    print("\n[3/4] Obteniendo token de Canvas...")
    access_token = get_valid_canvas_token(user)
    if access_token:
        print(f"  Token obtained: {access_token[:50]}...")
    else:
        print("  [ERROR] No valid token")
        sys.exit(0)
    
    # 4. Procesar items
    print("\n[4/4] Extrayendo contenido de archivos...")
    rag_service = get_rag_service()
    modules = course.modules.all()
    
    success = 0
    fail = 0
    
    for module in list(modules)[:1]:  # Just first module
        items = module.items.all()
        
        print(f"\n  Module: {module.name}")
        print(f"  Items: {len(items)}")
        
        for item in list(items)[:1]:  # Just first item per module
            print(f"\n    Item: {item.title}")
            print(f"    Type: {item.get_item_type_display()}")
            print(f"    URL:  {item.url[:80] if item.url else 'None'}...")
            
            if item.url:
                try:
                    extracted = rag_service._extract_text_from_file(item.url, access_token)
                    
                    if extracted:
                        success += 1
                        print(f"    [SUCCESS] {len(extracted)} chars extracted")
                        if len(extracted) > 200:
                            print(f"    Preview: {extracted[:200]}...")
                    else:
                        fail += 1
                        print(f"    [FAILED] No content extracted (returned None)")
                except Exception as e:
                    fail += 1
                    print(f"    [ERROR] {type(e).__name__}: {str(e)[:100]}")
    
    # Summary
    print(f"\n" + "="*80)
    print(f"RESUMEN")
    print(f"="*80)
    print(f"Extracciones exitosas: {success}")
    print(f"Extracciones fallidas: {fail}")
    
    if success > 0:
        print(f"\n[OK] EXITO: {success} archivo(s) extraido(s) correctamente!")
    else:
        print(f"\n[FAIL] PROBLEMA: No se extrajeron archivos")

except Exception as e:
    print(f"\n[CRITICAL ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
