#!/usr/bin/env python
"""
Test script to verify that multiple embeddings are created per document
and that search retrieves multiple results.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.rag_service import get_rag_service
from tu_app.models import Course, Module
from django.contrib.auth import get_user_model
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

print("=" * 70)
print("TESTING MULTIPLE EMBEDDINGS PER DOCUMENT")
print("=" * 70)

try:
    # Get RAG service
    rag_service = get_rag_service()
    
    # Test the chunking function with various sizes
    print("\n📊 TESTING CHUNKING FUNCTION:")
    print("-" * 70)
    
    test_texts = [
        ("Small text (100 chars)", "a" * 100),
        ("Medium text (500 chars)", "b" * 500),
        ("Large text (3000 chars)", "c" * 3000),
        ("Very large text (8000 chars)", "d" * 8000),
    ]
    
    for label, text in test_texts:
        chunks = rag_service._chunk_text(text, chunk_size=2000, overlap=400)
        print(f"✅ {label} → {len(chunks)} chunks")
    
    # Check current embeddings
    print("\n📁 CURRENT EMBEDDINGS STATE:")
    print("-" * 70)
    
    embeddings_dir = os.path.join(os.path.dirname(__file__), '.embeddings')
    if os.path.exists(embeddings_dir):
        files = os.listdir(embeddings_dir)
        print(f"✅ Found {len(files)} embeddings files")
        
        if files:
            import json
            for file in files[:3]:  # Show first 3
                filepath = os.path.join(embeddings_dir, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        doc_count = len(data.get('documents', []))
                        print(f"   • {file}: {doc_count} chunks/docs")
                except Exception as e:
                    print(f"   • {file}: ERROR - {e}")
    else:
        print("⚠️  No embeddings directory found yet")
    
    # Test search retrieval
    print("\n🔍 TESTING SEARCH RETRIEVAL:")
    print("-" * 70)
    
    courses = Course.objects.filter(user__username='admin').first()
    if courses:
        modules = courses.modules.all()
        if modules:
            module = modules.first()
            print(f"Using module: {module.name} (ID: {module.id})")
            
            test_query = "investigación"
            print(f"Searching for: '{test_query}'")
            
            results = rag_service.search_context(test_query, module.id, courses.id, top_k=5)
            print(f"\n✅ Retrieved {len(results)} documents:")
            for i, doc in enumerate(results, 1):
                title = doc.get('metadata', {}).get('item_title', 'Unknown')
                score = doc.get('relevance_score', 0)
                preview = doc.get('content', '')[:100]
                print(f"   {i}. [{score:.3f}] {title}")
                print(f"      Preview: {preview}...")
        else:
            print("⚠️  No modules found for admin user")
    else:
        print("⚠️  No courses found for admin user")

except Exception as e:
    logger.error(f"Error in test: {e}", exc_info=True)
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
