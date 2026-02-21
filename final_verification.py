#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Final verification script - complete RAG pipeline test
"""

import os
import sys
import django
import json
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.models import Course, Module
from tu_app.rag_service import get_rag_service
from tu_app.canvas_auth import get_valid_canvas_token

print("\n" + "="*80)
print("VERIFYING COMPLETE RAG PIPELINE")
print("="*80)

try:
    # Get first course with user
    course = Course.objects.first()
    if not course:
        print("[ERROR] No courses found")
        sys.exit(1)
    
    user = course.user
    print(f"\nCourse: {course.name} (User: {user.username})")
    
    # Get token
    access_token = get_valid_canvas_token(user)
    if not access_token:
        print("[ERROR] No valid token")
        sys.exit(1)
    
    # Get first module
    module = Module.objects.filter(course=course).first()
    if not module:
        print("[ERROR] No modules found")
        sys.exit(1)
    
    print(f"Module: {module.name} (ID: {module.id})")
    items = module.items.all()
    print(f"Items: {len(items)}")
    
    # Initialize RAG service
    rag_service = get_rag_service()
    
    # Analyze module
    print(f"\n[STARTING ANALYSIS]")
    success = rag_service.analyze_module(module, access_token)
    
    if not success:
        print("[FAILED] analyze_module returned False")
        sys.exit(1)
    
    # Check embeddings
    print(f"\n[CHECKING RESULTS]")
    collection_name = f"module_{module.id}_course_{module.course.id}"
    embeddings_count = rag_service.get_embeddings_count(collection_name)
    
    print(f"Collection: {collection_name}")
    print(f"Embeddings count: {embeddings_count}")
    
    # Check JSON file
    json_path = os.path.join(rag_service.json_embeddings_dir, f"{collection_name}.json")
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            num_chunks = len(data.get('documents', []))
            total_chars = sum(len(d) for d in data.get('documents', []))
            
            print(f"\nJSON File: {json_path}")
            print(f"  Total chunks: {num_chunks}")
            print(f"  Total chars: {total_chars}")
            
            if num_chunks > 1:
                print(f"\n  [SUCCESS] Multiple embeddings created!")
                for i, (doc, meta) in enumerate(zip(data.get('documents', [])[:5], data.get('metadatas', [])[:5])):
                    print(f"    Chunk {i+1}: {len(doc)} chars")
                    if meta:
                        print(f"             Meta: {json.dumps(meta)[:100]}")
            else:
                print(f"\n  [WARNING] Only {num_chunks} chunk(s) created")
    else:
        print(f"[WARNING] JSON file not found: {json_path}")
    
    # Summary
    print("\n" + "="*80)
    if embeddings_count > 1:
        print(f"RESULT: SUCCESS - {embeddings_count} embeddings created")
    elif embeddings_count == 1:
        print(f"RESULT: PARTIAL - 1 embedding created (expected multiple)")
    else:
        print(f"RESULT: FAILED - {embeddings_count} embeddings")
    print("="*80)

except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print()
