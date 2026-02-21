#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para diagnosticar por qué los PDFs no se están extrayendo.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.models import Course, Module, ModuleItem
from tu_app.rag_service import get_rag_service
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("DIAGNOSTICO: PDF EXTRACTION")
print("="*80)

# Obtener primer módulo con items
try:
    course = Course.objects.filter(user__username='admin').first()
    if not course:
        print("[WARN] No admin user courses found")
        sys.exit(0)
    
    modules = course.modules.all()
    print(f"\n[OK] Found {len(modules)} modules for course")
    
    # Buscar el primer módulo con items
    for module in modules[:2]:
        items = module.module_items.all()
        print(f"\n[MODULE] {module.name} (ID: {module.id})")
        print(f"   - Items total: {len(items)}")
        
        for item in items[:3]:
            print(f"\n   [ITEM] {item.title}")
            print(f"      - Type: {item.get_item_type_display()}")
            print(f"      - URL: {item.url[:100] if item.url else 'None'}...")
            print(f"      - Has content: {bool(item.url)}")
            
            # Intentar extractar
            if item.url:
                rag_service = get_rag_service()
                
                # Obtener token del usuario
                from tu_app.canvas_auth import get_valid_canvas_token
                user = course.user
                token_obj = get_valid_canvas_token(user)
                access_token = token_obj.access_token if token_obj else None
                
                print(f"\n      [EXTRACT] Attempting extraction...")
                print(f"      - Has token: {bool(access_token)}")
                
                extracted = rag_service._extract_text_from_file(item.url, access_token)
                
                if extracted:
                    print(f"      [OK] Extracted {len(extracted)} chars")
                    print(f"      [PREVIEW] {extracted[:200]}...")
                else:
                    print(f"      [FAIL] Extraction returned None")

except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    print(f"[ERROR] {e}")

print("\n" + "="*80)
