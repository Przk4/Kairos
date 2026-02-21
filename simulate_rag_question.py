#!/usr/bin/env python
"""
Simulación visual del flujo completo:
1. Usuario carga PDF (análisis)
2. Usuario hace pregunta (embedding de pregunta)
3. Comparación similitud con chunks
4. Contexto enviado a DeepSeek
"""

import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from tu_app.rag_service import get_rag_service
from tu_app.ai_service_config import DeepSeekProvider
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

logging.basicConfig(level=logging.WARNING)

print("\n" + "="*90)
print("🎬 SIMULACIÓN COMPLETA DEL FLUJO RAG")
print("="*90)

# Obtener RAG service
rag_service = get_rag_service()

# Cargar colección
collection_name = "module_2_course_1"

if collection_name not in rag_service.in_memory_db:
    print("\n⚠️  No hay documentos analizados en este módulo.")
    print("Necesitas hacer clic en 'Analyze Module' en la web para crear los embeddings.")
    print("Después podrás probar este script.\n")
    sys.exit(0)

collection = rag_service.in_memory_db[collection_name]

if not collection['documents']:
    print("\n❌ La colección está vacía\n")
    sys.exit(0)

print(f"\n📂 Módulo: {collection_name}")
print(f"📊 Total de chunks analizados: {len(collection['documents'])}")

# ======================================================================
# SIMULAR: Usuario hace pregunta
# ======================================================================

question = "¿Cuál es el objetivo principal de la investigación?"
print(f"\n🟦 USUARIO PREGUNTA: \"{question}\"")

# ======================================================================
# PASO 1: Calcular embedding de la pregunta
# ======================================================================

print("\n┌─────────────────────────────────────────────────────────────┐")
print("│ 1️⃣  CALCULAR EMBEDDING DE LA PREGUNTA                      │")
print("│    (usando sentence-transformers/all-MiniLM-L6-v2)          │")
print("└─────────────────────────────────────────────────────────────┘")

question_embedding = rag_service.embedding_model.encode(question).tolist()
print(f"\n✅ Embedding calculado:")
print(f"   • Dimensiones: {len(question_embedding)}")
print(f"   • Primeras 10: {[round(x, 4) for x in question_embedding[:10]]}")
print(f"   • Norma: {np.linalg.norm(question_embedding):.4f}")

# ======================================================================
# PASO 2: Comparar con cada chunk (similitud coseno)
# ======================================================================

print("\n┌─────────────────────────────────────────────────────────────┐")
print("│ 2️⃣  COMPARAR CON CADA CHUNK (similitud coseno)            │")
print("└─────────────────────────────────────────────────────────────┘")

similarities = []
for i, chunk_emb in enumerate(collection['embeddings']):
    sim = float(cosine_similarity([question_embedding], [chunk_emb])[0][0])
    similarities.append(sim)
    chunk_metadata = collection['metadatas'][i]
    print(f"\n   Chunk {i+1}:")
    print(f"      Título: {chunk_metadata.get('item_title', 'N/A')}")
    print(f"      Índice: {chunk_metadata.get('chunk_index', '0')}/{chunk_metadata.get('chunk_total', '1')}")
    print(f"      Similitud: 🟢 {sim:.4f}")
    print(f"      Preview: {collection['documents'][i][:100]}...")

# ======================================================================
# PASO 3: Seleccionar top chunks mas similares
# ======================================================================

print("\n┌─────────────────────────────────────────────────────────────┐")
print("│ 3️⃣  SELECCIONAR TOP 5 CHUNKS MAS SIMILARES                 │")
print("└─────────────────────────────────────────────────────────────┘")

top_k = 5
top_indices = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)[:top_k]

context_list = []
for rank, idx in enumerate(top_indices, 1):
    doc = collection['documents'][idx]
    metadata = collection['metadatas'][idx]
    sim = similarities[idx]
    
    context_list.append({
        'content': doc,
        'metadata': metadata,
        'relevance_score': sim
    })
    
    print(f"\n   🥇 #{rank} - Similitud: {sim:.4f}")
    print(f"      Título: {metadata.get('item_title', 'N/A')}")
    print(f"      Chunk: {metadata.get('chunk_index', '0')}/{metadata.get('chunk_total', '1')}")
    print(f"      Contenido: {doc[:120]}...")

# ======================================================================
# PASO 4: Formatear contexto para DeepSeek
# ======================================================================

print("\n┌─────────────────────────────────────────────────────────────┐")
print("│ 4️⃣  FORMATEAR CONTEXTO PARA DEEPSEEK                      │")
print("│    (contenido COMPLETO, no limitado a 200 chars)           │")
print("└─────────────────────────────────────────────────────────────┘")

provider = DeepSeekProvider()
formatted_context = provider._format_context(context_list)

print(f"\n✅ Contexto formateado:")
print(f"   • Total caracteres: {len(formatted_context)}")
print(f"   • Total líneas: {len(formatted_context.splitlines())}")
print(f"   • Primeras 500 caracteres:\n")
print("   " + "─" * 55)
for line in formatted_context[:600].splitlines()[:10]:
    print(f"   {line}")
print("   " + "─" * 55)

# ======================================================================
# PASO 5: Mostrar prompt que se enviaría a DeepSeek
# ======================================================================

print("\n┌─────────────────────────────────────────────────────────────┐")
print("│ 5️⃣  PROMPT FINAL QUE SE ENVÍA A DEEPSEEK API              │")
print("└─────────────────────────────────────────────────────────────┘")

system_prompt = provider.SYSTEM_PROMPT
final_prompt = f"""Contexto del curso:
{formatted_context}

Pregunta del estudiante:
{question}

Por favor, responde basándote en el contexto proporcionado."""

print(f"\n📝 System Prompt:")
print("   " + "─" * 55)
for line in system_prompt.splitlines()[:5]:
    print(f"   {line}")
print("   ...")
print("   " + "─" * 55)

print(f"\n📝 User Message:")
print("   " + "─" * 55)
print(final_prompt[:500])
print("   ...")
print("   " + "─" * 55)

print(f"\n📊 Estadísticas:")
print(f"   • Total caracteres en sistema: {len(system_prompt)}")
print(f"   • Total caracteres en contexto: {len(formatted_context)}")
print(f"   • Total caracteres en pregunta: {len(question)}")
print(f"   • TOTAL: {len(system_prompt) + len(formatted_context) + len(question)} caracteres")
print(f"   • Chunks enviados: {len(context_list)} de {len(collection['documents'])}")

# ======================================================================
# RESUMEN
# ======================================================================

print("\n" + "="*90)
print("✅ FLUJO COMPLETADO")
print("="*90)

print("""
📋 RESUMEN:

1. 📥 Usuario carga PDF → Se chunka en 2000 chars con 400 overlap
2. 🧠 Cada chunk → Embedding de 384 dimensiones
3. ❓ Usuario pregunta → Embedding de 384 dimensiones  
4. 🔍 Comparación → Similitud coseno entre pregunta y cada chunk
5. 🏆 Selección → Top 5 chunks más similares
6. 📄 Formateo → Contexto completo (no limitado a 200 chars)
7. 🤖 DeepSeek → Recibe contexto completo + pregunta
8. 💬 Respuesta → Basada en los chunks más relevantes

✨ RESULTADO: Respuesta de mejor calidad porque:
   • DeepSeek lee TODOS los chunks relevantes, no solo 200 chars
   • Chunks seleccionados por similitud coseno (exactitud)
   • Contexto formateado de forma clara con referencias de relevancia
""")

print("="*90 + "\n")
