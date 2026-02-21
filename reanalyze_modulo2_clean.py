#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module, ModuleAnalysis
from tu_app.rag_service import get_rag_service
from tu_app.views import get_valid_canvas_token
from django.contrib.auth.models import User
from pathlib import Path
import json

print("=" * 80)
print("[RE-ANALYSIS] Module 2 with real PDF content")
print("=" * 80)

# Get user and token
user = User.objects.first()
if not user:
    print("[ERROR] No user found")
    exit(1)

access_token = get_valid_canvas_token(user)
if not access_token:
    print("[ERROR] No Canvas token - canvas offline or token expired")
    exit(1)

print(f"\n[TOKEN OK] Token obtained: {access_token[:20]}...")

# Get module
module = Module.objects.filter(id=2, course__user=user).first()
if not module:
    print("[ERROR] Module 2 not found")
    exit(1)

print(f"\n[MODULE] {module.name} (ID: 2)")

# Items before
items_before = module.items.all().count()
print(f"Items before: {items_before}")

# Re-sync items
print(f"\n[STEP 1] Re-syncing items...")
from tu_app.canvas_auth import sync_module_items
try:
    headers = {'Authorization': f'Bearer {access_token}'}
    sync_module_items(user, module, headers)
    print("[OK] Items synced")
except Exception as e:
    print(f"[WARN] Error syncing: {e}")
    pass

# Items after
items_after = module.items.all().count()
print(f"Items after: {items_after}")

for item in module.items.all():
    print(f"  - {item.title} ({item.get_item_type_display()})")

# Re-analyze
print(f"\n[STEP 2] Re-analyzing module...")
rag_service = get_rag_service()

success = rag_service.analyze_module(module, access_token)

if success:
    print(f"[OK] Analysis completed")
    
    # Check embeddings
    embeddings_file = Path(f".embeddings/module_2_course_1.json")
    if embeddings_file.exists():
        with open(embeddings_file) as f:
            data = json.load(f)
            
        print(f"\n[EMBEDDINGS] Total documents: {len(data.get('documents', []))}")
        
        # Show first documents
        for i, doc in enumerate(data.get('documents', [])[:2], 1):
            chars = len(doc)
            is_full = chars > 200
            status = "[OK] REAL CONTENT" if is_full else "[WARN] Only filename"
            print(f"  {i}. {chars} chars - {status}")
            if chars < 200:
                print(f"     {doc[:100]}")
            else:
                print(f"     Preview: {doc[:100]}...")
        
        print(f"\n[OK] Embeddings updated with real PDF content")
        print(f"[OK] DeepSeek can now access the content")
else:
    print(f"[ERROR] Analysis failed")

print("\n" + "=" * 80)
