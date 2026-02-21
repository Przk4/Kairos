#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar que el chunking y embeddings están funcionando correctamente.
Permite simular un PDF extraído y ver cuántos embeddings se generan.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.rag_service import get_rag_service
import json
from pathlib import Path

print("\n" + "="*80)
print("TEST: VERIFICAR CHUNKING Y EMBEDDINGS MULTIPLES")
print("="*80)

rag_service = get_rag_service()

# Test 1: Chunking con diferentes tamaños
print("\nTEST 1: Funcion _chunk_text()")
print("-"*80)

test_cases = [
    ("Pequeno (100 chars)", "a" * 100),
    ("Mediano (800 chars)", "b" * 800),
    ("Grande (2000 chars)", "c" * 2000),
    ("Muy grande (5000 chars)", "d" * 5000),
    ("Extra grande (10000 chars)", "e" * 10000),
]

for label, text in test_cases:
    chunks_1000_300 = rag_service._chunk_text(text, chunk_size=1000, overlap=300)
    chunks_500_150 = rag_service._chunk_text(text, chunk_size=500, overlap=150)
    print(f"\n[OK] {label}")
    print(f"   - Con chunk_size=1000, overlap=300: {len(chunks_1000_300)} chunks")
    print(f"   - Con chunk_size=500, overlap=150:  {len(chunks_500_150)} chunks")
    
    # Verificar que al menos el chunk no está vacío
    if chunks_1000_300:
        print(f"   - Primer chunk: {len(chunks_1000_300[0])} chars")

# Test 2: Verificar embeddings guardados
print("\n\nTEST 2: Embeddings guardados en .embeddings/")
print("-"*80)

embeddings_dir = Path('.embeddings')
if embeddings_dir.exists():
    files = list(embeddings_dir.glob('*.json'))
    print(f"[OK] Encontrados {len(files)} archivos JSON")
    
    for json_file in files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            docs = data.get('documents', [])
            print(f"\n[FILE] {json_file.name}")
            print(f"   - Total chunks: {len(docs)}")
            if docs:
                for i, doc in enumerate(docs[:3]):
                    print(f"   - Chunk {i+1}: {len(doc)} chars")
                if len(docs) > 3:
                    print(f"   - ... y {len(docs)-3} mas")
else:
    print("[WARN] Directorio .embeddings no existe")

# Test 3: Verificar colecciones en memoria
print("\n\nTEST 3: Colecciones en memoria")
print("-"*80)

if rag_service.in_memory_db:
    for collection_name, collection in rag_service.in_memory_db.items():
        docs = collection.get('documents', [])
        embeddings = collection.get('embeddings', [])
        print(f"\n[OK] {collection_name}")
        print(f"   - Documentos/Chunks: {len(docs)}")
        print(f"   - Embeddings: {len(embeddings)}")
        
        if docs:
            for i, doc in enumerate(docs[:3]):
                print(f"   - Chunk {i+1}: {len(doc)} chars")
            if len(docs) > 3:
                print(f"   - ... y {len(docs)-3} mas")
else:
    print("[WARN] No hay colecciones en memoria")

# Test 4: Simular lo que pasa en analyze_module()
print("\n\nTEST 4: Simulacion del analisis de un documento")
print("-"*80)

# Simulando un documento con título + contenido extraído
item_title = "Proyecto de investigacion (replanteado) (2).pdf"
item_type = "Archivo"
extracted_text = "Lorem ipsum dolor sit amet. " * 50  # Texto simulado de ~1400 chars

# Lo que hace analyze_module():
text = f"{item_title} - {item_type}"
print(f"\nDato inicial: '{text[:60]}...' ({len(text)} chars)")

text = f"{text}\n\n{extracted_text}"
print(f"Despues de agregar contenido: '{text[:60]}...' ({len(text)} chars)")

# Chunking con logika mejorada
extracted = extracted_text
if extracted:
    chunks = rag_service._chunk_text(text, chunk_size=1000, overlap=300)
    
    # Forzar al menos 2 chunks si es contenido extraído
    if len(chunks) == 1 and len(chunks[0]) > 500:
        print(f"\n[FORCE] Solo 1 chunk pero contenido > 500 chars, re-chunkando...")
        chunks = rag_service._chunk_text(chunks[0], chunk_size=500, overlap=150)
    
    print(f"\n[OK] Resultado del chunking:")
    print(f"   - Chunks generados: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"   - Chunk {i+1}: {len(chunk)} chars")

print("\n" + "="*80)
print("TEST COMPLETADO")
print("="*80)
print("\nPROXIMOS PASOS:")
print("   1. Ve a la web")
print("   2. Abre un modulo con PDFs")
print("   3. Haz clic en 'Analyze Module'")
print("   4. Verifica que se generan multiples embeddings")
print("   5. Usa POST /api/debug/question-embeddings/ para ver similitud")
