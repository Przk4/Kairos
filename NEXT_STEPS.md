# 🎬 PRÓXIMOS PASOS - GUÍA DE ACCIÓN

## ¿QUÉ HACER AHORA?

### Opción A: Probar en la Web (Recomendado)

#### 1. **Re-analizar un módulo**
```
1. Abre la web: http://localhost:8000/
2. Navega a un módulo con PDFs (ej: Módulo 2)
3. Haz clic en el botón: "Analyze Module"
4. Espera a que termine (verás: "Analysis Completed ✅")
```

**¿Qué está pasando?**
- El código descarga los PDFs de Canvas
- Los extrae con pdfplumber (solo texto, sin imágenes)
- Los divide en CHUNKS de 2000 caracteres
- Crea EL EMBEDDING para CADA chunk
- Los guarda en `.embeddings/module_X_course_Y.json`

**Ejemplo**:
```
PDF (4500 chars) → 3 chunks:
  • Chunk 0: 2000 chars → Embedding A
  • Chunk 1: 2000 chars → Embedding B  
  • Chunk 2: 500 chars  → Embedding C
```

---

#### 2. **Hacer una pregunta en el Chat IA**
```
1. Ve a "Chat IA" (pestaña del módulo)
2. Escribe: "¿Cuáles son los objetivos del proyecto?"
3. Presiona Enter
```

**¿Qué está pasando?**
- Tu pregunta se convierte en EMBEDDING (384 dimensiones)
- Se COMPARA con CADA chunk (similitud coseno)
- Se seleccionan los TOP 5 chunks más similares
- Se envía CONTEXTO COMPLETO a DeepSeek API
- DeepSeek responde basándose en los chunks relevantes

**Ejemplo**:
```
Tu pregunta: "¿Cuáles son los objetivos?"
  ↓
Embedding: [-0.15, 0.23, ..., 0.08] (384 números)
  ↓
Comparar:
  • Chunk A (objetivo): similitud 0.92 ✅ MÁS RELEVANTE
  • Chunk B (definiciones): similitud 0.65 ✅ RELEVANTE
  • Chunk C (conclusiones): similitud 0.42 (MENOS)
  ↓
Enviar a DeepSeek: Chunks A + B
  ↓
Respuesta: Basada en contexto relevante
```

---

### Opción B: Verificar todo en Terminal

#### **Ver embeddings de una pregunta**

```bash
curl -X POST http://localhost:8000/api/debug/question-embeddings/ \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Qué es la investigación?",
    "module_id": 2,
    "course_id": 1
  }'
```

**Respuesta**:
```json
{
  "status": "ok",
  "question": "¿Qué es la investigación?",
  "question_embedding_dims": 384,
  "question_embedding_sample": [0.071, 0.031, -0.039, ...],
  "total_chunks_analyzed": 3,
  "similarities": {
    "min": 0.325,
    "max": 0.951,
    "mean": 0.642
  },
  "top_matches": [
    {
      "rank": 1,
      "similarity": 0.951,
      "title": "PDF - Investigación",
      "chunk_index": "0",
      "chunk_total": "3",
      "preview": "La investigación académica..."
    }
  ]
}
```

---

#### **Ver estado del análisis anterior**

```bash
curl http://localhost:8000/api/debug/prompt-flow/
```

Muestra:
- Última pregunta hecha
- Chunks recuperados
- Similitud de cada chunk
- Respuesta de DeepSeek

---

## 🔍 VERIFICACIÓN - "¿Está funcionando?"

### ✅ Señales de que funciona correctamente:

1. **Verificar chunks creados**:
   ```bash
   ls -la .embeddings/
   # Deberías ver: module_2_course_1.json (con múltiples chunks)
   ```

2. **Verificar en la web**:
   - [ ] El botón "Analyze Module" muestra "Analyzing..." durante el análisis
   - [ ] El botón cambia a "Analysis Completed ✅" cuando termina
   - [ ] Puedes hacer preguntas en el Chat IA

3. **Verificar embedding de pregunta**:
   ```bash
   # Haz una pregunta en el chat
   # Ve a: /api/debug/prompt-flow/
   # Deberías ver retrieved_docs con similitudes
   ```

4. **Verificar en terminal**:
   ```bash
   python verify_rag_flow.py
   # Deberías ver: "✅ Contexto formateado: ... caracteres"
   ```

---

## ⚠️ SI ALGO SALE MAL

### **Error: "No hay documentos analizados"**
- **Causa**: El módulo aún no ha sido analizado
- **Solución**: Haz clic en "Analyze Module" en la web y espera

### **Error: "Colección vacía"** en /api/debug/question-embeddings/
- **Causa**: `.embeddings/module_X_course_Y.json` no existe o está vacío
- **Solución**: Re-analiza el módulo con el botón web

### **DeepSeek responde pero sin contexto...** relevante
- **Causa**: La similitud fue baja (todos los chunks < 0.5)
- **Solución**: Normal, DeepSeek intentará responder de todas formas

### **Error: "API key no configurada"**
- **Causa**: DEEPSEEK_API_KEY en `.env` no existe
- **Solución**: Agregar tu API key a `.env`

---

## 📊 COMPARACIÓN: ANTES vs AHORA

### ANTES (Código antiguo):
```
PDF → 1 chunk único → 1 embedding → DeepSeek (solo 200 chars)
❌ Poca información enviada
❌ Respuestas genéricas
❌ No hay similitud de pregunta-documento
```

### AHORA (Código nuevo):
```
PDF → 5 chunks → 5 embeddings → Similitud coseno → 
→ Top 5 chunks → Contexto COMPLETO → DeepSeek
✅ Más información
✅ Respuestas específicas
✅ Selección inteligente por similitud
✅ Dashboard para ver embeddings
```

---

## 🎯 CHECKLIST FINAL

Marca lo que ya verificaste:

- [ ] El código se actualiza con los cambios (revisar `rag_service.py` líneas 381-410)
- [ ] El servidor Django se inicia sin errores
- [ ] Haces clic en "Analyze Module" y completa exitosamente  
- [ ] Se crea `.embeddings/module_X_course_Y.json` con múltiples chunks
- [ ] Haces una pregunta en el Chat IA
- [ ] DeepSeek responde basándose en los chunks
- [ ] (Opcional) Llamas a `/api/debug/question-embeddings/` y ves el resultado

Si todo ✅, ¡LISTO! El sistema completo RAG funciona correctamente.

---

## 📞 RESUMEN TÉCNICO

**Flujo implementado**:
```python
# tu_app/rag_service.py - analyze_module()
if extracted:
    chunks = self._chunk_text(text, chunk_size=2000, overlap=400)  # ← NEW
    for chunk in chunks:                                           # ← NEW
        embedding = encoding_model.encode(chunk)                   # ← NEW

# tu_app/rag_service.py - search_context()  
query_embedding = encoding_model.encode(question)  # Pregunta
similarities = [cosine_similarity(q_emb, ch_emb) for ch_emb in chunk_embeddings]
top_chunks = sorted(...)[:top_k]

# tu_app/ai_service_config.py - _format_context()
contextfull_text = str(chunk['content'])  # ← SIN LIMITACIÓN (era: [:200])

# tu_app/views.py - debug_question_embeddings()  # ← NEW ENDPOINT
return JsonResponse({
    'question_embedding': q_embedding,
    'similarities': similarities,
    'top_matches': top_chunks,
})
```

---

**¡Listo para usar! 🚀**
