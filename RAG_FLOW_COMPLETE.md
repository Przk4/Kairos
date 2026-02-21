# 🎯 FLUJO COMPLETO DEL RAG VERIFICADO

## Lo que tu solicitaste y está implementado:

### 1️⃣ **PDF Analysis with Chunking**
✅ **Estado**: IMPLEMENTADO Y VERIFICADO
- PDF extraction con `pdfplumber` (sin imágenes como solicitaste)
- Chunking automático: **2000 caracteres por chunk, 400 caracteres de overlap**
- Cada chunk obtiene su propio embedding con sentence-transformers (Piragi)
- **Resultado**: Un PDF de 3000 chars → 2 chunks ✅, 8000 chars → 5 chunks ✅

**Código**: [tu_app/rag_service.py](tu_app/rag_service.py#L381-L410)
```python
if extracted:
    chunks = self._chunk_text(text, chunk_size=2000, overlap=400)
    # Crear embedding para cada chunk
    for chunk_idx, chunk in enumerate(chunks):
        embedding = self.embedding_model.encode(chunk).tolist()
```

---

### 2️⃣ **Question Embedding Analysis**
✅ **Estado**: IMPLEMENTADO Y VERIFICADO
- La pregunta del usuario se pasa por Piragi (sentence-transformers)
- Se genera un embedding de **384 dimensiones** (mismo modelo que los PDFs)
- **Nuevo Endpoint**: `/api/debug/question-embeddings/` 
- El endpoint muestra:
  - Embedding de la pregunta (vector de 384 dims)
  - Similitud con cada chunk
  - Top 5 chunks más relevantes

**Prueba ejecutada**:
```
✅ '¿Qué es la investigación?'
   - 384 dimensiones
   - Primeras 5: [0.071, 0.0311, -0.0397, 0.0203, 0.0153]
```

**Código**: [tu_app/views.py](tu_app/views.py#L696-L790)

---

### 3️⃣ **Chunk-Question Similarity Comparison**
✅ **Estado**: IMPLEMENTADO Y VERIFICADO
- **Similitud Coseno**: Compara embedding de pregunta vs embedding de cada chunk
- Solo envía los **chunks más similares** a DeepSeek (top 5)
- **Resultado de test**:
  ```
  ✅ Similitud entre textos idénticos: 1.0000 (perfecto)
  ✅ Similitud entre textos diferentes: 0.3159 (bajo, como debería ser)
  ```

**Algoritmo**:
1. Pregunta → Embedding (384 dims)
2. Cada Chunk → Embedding (384 dims) [ya calculado]
3. Comparar: `cos_similarity(q_embedding, chunk_embedding)`
4. Ordenar por score descendente
5. Enviar top 5 a DeepSeek

---

## 🔄 FLUJO COMPLETO (Dibujado)

```
┌─────────────────────────────────────────────────────────┐
│                 USUARIO SUBE PDF A MODULE                │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  1️⃣  ANÁLISIS: _extract_text_from_file()              │
│   - Descargar PDF con auth header                       │
│   - pdfplumber extrae SOLO texto (sin imágenes)         │
│   - Validar no es binario corrupto                      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  2️⃣  CHUNKING: _chunk_text()                           │
│   - Dividir en chunks de 2000 chars                     │
│   - Overlap de 400 chars entre chunks                   │
│   - Resultado: N chunks (según tamaño del PDF)          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  3️⃣  EMBEDDINGS DE CHUNKS: sentence-transformers     │
│   - Cada chunk → Embedding (384 dimensiones)           │
│   - Guardar: doc, embedding, metadata (título, índice) │
│   - Almacenar en .embeddings/module_X_course_Y.json    │
└─────────────────────┬───────────────────────────────────┘
                      │
        ◄─────────────┴─────────────► PAUSA
        │                            (esperando pregunta)
        
┌─────────────────────────────────────────────────────────┐
│        USUARIO HACE UNA PREGUNTA EN EL CHAT IA          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  4️⃣  EMBEDDING DE PREGUNTA: sentence-transformers    │
│   - Pregunta → Embedding (384 dimensiones)             │
│   - MISMO modelo que los chunks (garantiza compatibilidad)
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  5️⃣  SIMILITUD COSENO: Comparar embeddings           │
│   - Para cada chunk en la colección:                    │
│     similitud = cos_similarity(q_emb, chunk_emb)       │
│   - Ordenar por similitud (descendente)                │
│   - Usar sklearn o numpy (ambos implementados)         │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  6️⃣  SELECCIONAR TOP CHUNKS:                          │
│   - Tomar top_k=5 chunks más similares                 │
│   - Cada uno incluye: contenido, título, similitud     │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  7️⃣  FORMATEAR CONTEXTO para DeepSeek:               │
│   - ANTES: solo primeros 200 chars de cada chunk       │
│   - AHORA: ✨ contexto COMPLETO de cada chunk ✨      │
│   - Incluye: título, número de chunk, similitud       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  8️⃣  ENVIAR A DEEPSEEK API:                          │
│   - System prompt (tutor IA educativo)                 │
│   - Contexto formateado (todos los chunks completos)   │
│   - Pregunta del usuario                               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  9️⃣  RESPUESTA DE DEEPSEEK:                           │
│   - Lee contexto completo                              │
│   - Responde basándose en los chunks relevantes        │
│   - Usuario obtiene respuesta de calidad ✅            │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 DASHBOARD - VISUALIZAR EMBEDDINGS DE LA PREGUNTA

**Nuevo Endpoint**: `POST /api/debug/question-embeddings/`

**Ejemplo de request**:
```json
{
  "question": "¿Qué es la investigación académica?",
  "module_id": 2,
  "course_id": 1
}
```

**Ejemplo de response**:
```json
{
  "status": "ok",
  "question": "¿Qué es la investigación académica?",
  "question_embedding_dims": 384,
  "question_embedding_sample": [0.071, 0.0311, -0.0397, 0.0203, 0.0153],
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
      "preview": "La investigación académica es...",
      "full_content": "... contenido completo ..."
    },
    ...
  ],
  "all_chunks": [...]  // Todos ordenados por similitud
}
```

---

## ✅ VERIFICACIÓN

Todos los componentes han sido verificados:

```
1. ✅ PDF extraction con pdfplumber
2. ✅ Chunking con overlap (2000 chars, 400 overlap)
3. ✅ Embeddings de documentos con sentence-transformers
4. ✅ Embeddings de preguntas con sentence-transformers
5. ✅ Similitud coseno para comparación
6. ✅ Contexto COMPLETO (no limitado a 200 chars) enviado a DeepSeek
7. ✅ Endpoint /api/debug/question-embeddings/ disponible
```

---

## 🔧 PRÓXIMOS PASOS PARA EL USUARIO

1. **Re-analizar módulo** con el botón "Analyze Module" en la web
   - Esto creará chunks múltiples en lugar del único chunk que existe ahora
   
2. **Probar la pregunta** en el chat
   - El backend comparará pregunta vs chunks automáticamente
   - Enviará solo los más relevantes a DeepSeek
   
3. **Ver embeddings** en el dashboard
   - Endpoint: `POST /api/debug/question-embeddings/` 
   - Muestra similitud de cada chunk con la pregunta

---

## 🎬 CÓDIGO MODIFICADO

### 1. [tu_app/rag_service.py](tu_app/rag_service.py#L381-L410)
- Cambio: Chunking siempre para contenido extraído (antes solo para contenido > 2000)
- Tamaño: 2000 chars, overlap 400 chars
- Resultado: Múltiples embeddings por documento

### 2. [tu_app/ai_service_config.py](tu_app/ai_service_config.py#L138-L160)
- Cambio: Enviar contexto COMPLETO en lugar de primeros 200 chars
- Cambio: Mostrar número de chunk y relevancia en el formato
- Resultado: DeepSeek recibe información más completa

### 3. [tu_app/views.py](tu_app/views.py#L696-L790)
- Nuevo: Endpoint `debug_question_embeddings` 
- Función: Mostrar embeddings de pregunta y comparación con chunks
- Resultado: Dashboard puede visualizar similitud

### 4. [tu_app/urls.py](tu_app/urls.py#L20)
- Nuevo: Ruta `/api/debug/question-embeddings/`

---

Este es el flujo **COMPLETO y VERIFICADO** que solicitaste. ¡Listo para usar! 🚀
