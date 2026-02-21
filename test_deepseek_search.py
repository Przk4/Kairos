#!/usr/bin/env python
"""
Test DeepSeek search en los embeddings
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.rag_service import get_rag_service

print("=" * 80)
print("[TEST] DeepSeek RAG Search - Module 2")
print("=" * 80)

rag_service = get_rag_service()

# Test search query
query = "¿Cuál es el tema principal del proyecto de investigación?"
collection = "module_2_course_1"

print(f"\nQuery: {query}")
print(f"Collection: {collection}")
print("-" * 80)

# Buscar en embeddings
results = rag_service.search_documents(query, collection, k=3)

print(f"\n[RESULTADOS] Encontrados {len(results)} documentos relevantes:")
print("-" * 80)

for i, (doc, score) in enumerate(results, 1):
    print(f"\n{i}. Similarity: {score:.3f}")
    print(f"   Preview: {doc[:150]}...")

if results:
    print(f"\n[OK] DeepSeek puede acceder a los documentos")
    print(f"[OK] Los embeddings contienen contenido buscable del PDF")
else:
    print(f"\n[WARN] No results found - check if collection is loaded")

print("\n" + "=" * 80)
