# 🔍 Guía de Debugging - Kairos AI Tutoring System

## ¿Qué hay adentro?

He creado un sistema completo de debugging y monitoring para que veas **exactamente** qué está sucediendo adentro del sistema. No es código integrado en la aplicación, sino herramientas *diagnósticas* especiales para desarrolladores.

## 📊 Tres Formas de Ver lo que Sucede

### 1. 🎨 **Dashboard Visual en Tiempo Real** (RECOMENDADO)
**URL:** `http://127.0.0.1:8000/debug/dashboard/`

Este es el lugar perfecto para ver todo de una forma visual hermosa:

- **Estadísticas en Vivo**: Módulos analizados, embeddings generados, llamadas a DeepSeek
- **Eventos Filtrados**: Ver solo eventos de RAG, DeepSeek, Embeddings, o Errores
- **Base de Datos en Memoria**: Ver exactamente qué colecciones existen y cuántos documentos tienen
- **Auto-refresh**: Se actualiza automáticamente cada 2 segundos

Características:
- 🔄 Autorefresh automático
- 🎯 Filtros por tipo de evento
- 📈 Estadísticas en tiempo real
- 💾 Ver colecciones en memoria

### 2. 📡 **API JSON para Eventos**
**URL:** `http://127.0.0.1:8000/api/debug/events/?type=RAG&limit=50`

Obtén eventos en formato JSON directamente:

```bash
# Ver todos los eventos
curl http://127.0.0.1:8000/api/debug/events/

# Ver solo eventos de RAG
curl http://127.0.0.1:8000/api/debug/events/?type=RAG

# Ver solo errores
curl http://127.0.0.1:8000/api/debug/events/?type=ERROR

# Aumentar límite
curl http://127.0.0.1:8000/api/debug/events/?limit=200
```

**Parámetros:**
- `type`: Filtrar por `RAG`, `DEEPSEEK`, `EMBEDDING`, `MEMORY_DB`, `ERROR`
- `limit`: Número de eventos (default: 50)

**Respuesta ejemplo:**
```json
{
  "status": "ok",
  "events": [
    {
      "timestamp": "2026-02-16T14:30:45.123456",
      "type": "RAG",
      "message": "🔍 Iniciando análisis de módulo: Matemáticas 101",
      "data": {
        "module_id": 2,
        "module_name": "Matemáticas 101",
        "action": "start"
      }
    },
    {
      "timestamp": "2026-02-16T14:30:50.654321",
      "type": "EMBEDDING",
      "message": "📊 Embedding creado: Teorema de Pitágoras (dim: 384)",
      "data": {
        "item_id": 45,
        "title": "Teorema de Pitágoras",
        "dimensions": 384
      }
    }
  ],
  "total_events": 156,
  "event_type_filter": "RAG"
}
```

### 3. 📈 **API JSON para Estadísticas**
**URL:** `http://127.0.0.1:8000/api/debug/stats/`

Obtén estadísticas agregadas del sistema:

```bash
curl http://127.0.0.1:8000/api/debug/stats/
```

**Respuesta ejemplo:**
```json
{
  "status": "ok",
  "timestamp": "2026-02-16T14:35:22.123456",
  "rag": {
    "modules_analyzed": 5,
    "total_embeddings": 72,
    "collections_created": 0,
    "last_analysis": "2026-02-16T14:32:10.654321"
  },
  "deepseek": {
    "total_calls": 12,
    "total_tokens": 4856,
    "avg_response_time": 2345.67,
    "last_call": "2026-02-16T14:33:45.987654"
  },
  "memory_db": {
    "collections": {
      "module_2_course_1": {
        "docs": 8,
        "embeddings": 8,
        "updated": "2026-02-16T14:32:10.654321"
      },
      "module_5_course_1": {
        "docs": 12,
        "embeddings": 12,
        "updated": "2026-02-16T14:30:45.123456"
      }
    }
  },
  "event_counts": {
    "RAG": 45,
    "DEEPSEEK": 12,
    "EMBEDDING": 72,
    "MEMORY_DB": 8,
    "ERROR": 0
  }
}
```

## 🎯 Cómo Funciona

### Stages de Debugging

```
Usuario hace una pregunta
    ↓
[RAG] Busqueda en base de conocimiento
  └─ log: "🔎 Búsqueda RAG: 'pregunta' → 3 resultados"
  └─ data: {query, module_id, results}
    ↓
[DEEPSEEK] Llamada a API
  └─ log: "🤖 Respuesta de DeepSeek (1234ms)"
  └─ data: {prompt, response, tokens, response_time_ms, total_calls}
    ↓
[RESPUESTA] Al usuario
```

### Tipos de Eventos

| Tipo | Emoji | Qué significa | Ejemplo |
|------|-------|--------------|---------|
| **RAG** | 🔍 | Búsquedas en la base de conocimiento | "Iniciando análisis de módulo", "Búsqueda RAG: 'pregunta' → 3 resultados" |
| **DEEPSEEK** | 🤖 | Llamadas a la IA | "Respuesta de DeepSeek (1234ms)" |
| **EMBEDDING** | 📊 | Créación de embeddings | "Embedding creado: 'Título' (dim: 384)" |
| **MEMORY_DB** | 💾 | Operaciones en base de datos en memoria | "Colección actualizada: module_2_course_1" |
| **ERROR** | ❌ | Problemas detectados | "Error procesando item 45" |

## 📋 Qué Puedes Ver

### 1. Estado del RAG Service
```json
{
  "modules_analyzed": 5,          // Cuántos módulos han sido analizados
  "total_embeddings": 72,         // Cuántos embeddings se crearon
  "collections_created": 0,       // Cuántas colecciones ChromaDB
  "last_analysis": "2026-02-16T..." // Cuándo fue la última búsqueda
}
```

### 2. Estadísticas de DeepSeek
```json
{
  "total_calls": 12,              // Total de llamadas a la IA
  "total_tokens": 4856,           // Total de tokens gastados
  "avg_response_time": 2345.67,   // Tiempo promedio de respuesta (ms)
  "last_call": "2026-02-16T..."   // Última llamada realizada
}
```

### 3. Estado de la Base de Datos en Memoria
```json
{
  "collections": {
    "module_2_course_1": {
      "docs": 8,                  // Documentos en esta colección
      "embeddings": 8,            // Embeddings calculados
      "updated": "2026-02-16T..." // Cuándo se actualizó
    }
  }
}
```

## 🚀 Casos de Uso

### Caso 1: Quiero saber si el RAG está guardando documentos correctamente
```
1. Haz clic en "Analizar" en un módulo
2. Abre http://127.0.0.1:8000/debug/dashboard/
3. Busca en "Base de Datos en Memoria" la colección corresponiente
4. Verifica que tenga documentos = embeddings
```

### Caso 2: Quiero ver qué le estoy enviando a DeepSeek y qué me devuelve
```
1. Haz una pregunta en el chat
2. Ve a http://127.0.0.1:8000/api/debug/events/?type=DEEPSEEK
3. Busca el evento más reciente tipo DEEPSEEK
4. Ve los detalles de prompt y response en "data"
```

### Caso 3: Quiero detectar errores en el análisis de módulos
```
1. Haz clic en "Analizar"
2. Ve a http://127.0.0.1:8000/api/debug/events/?type=ERROR
3. Si hay errores, ves exactamente qué salió mal
```

### Caso 4: Quiero monitorear en tiempo real todo lo que está pasando
```
1. Abre http://127.0.0.1:8000/debug/dashboard/ en una ventana
2. Realiza acciones en la app (analizar, hacer preguntas)
3. El dashboard se actualiza automáticamente cada 2 segundos
```

## 🛠️ Integración con el Código

El debugging está integrado en:

### `tu_app/debug_service.py`
- `get_debug_service()` - Obtiene la instancia singleton
- `log_rag_analysis_start()` - Log cuando inicia análisis
- `log_rag_analysis_complete()` - Log cuando termina
- `log_embedding_created()` - Log de cada embedding
- `log_deepseek_call()` - Log de respuestas DeepSeek
- `log_error()` - Log de errores
- `get_recent_events()` - Obtiene eventos filtrados
- `get_stats()` - Obtiene estadísticas agregadas

### `tu_app/rag_service.py`
Integración en:
- `analyze_module()` - Logs de inicio, fin, y errores
- `search_context()` - Logs de búsquedas RAG
- Cada embedding creado se registra

### `tu_app/ai_service.py`
Integración en:
- `answer_question()` - Logs de llamadas a DeepSeek con respuestas

### `tu_app/views.py`
Tres nuevos endpoints:
- `/api/debug/events/` - API JSON de eventos
- `/api/debug/stats/` - API JSON de estadísticas
- `/debug/dashboard/` - Dashboard visual

## 📝 Logs a Nivel de Sistema

Además de los endpoints especiales, también abro logs estándar de Django:

```
[16/Feb/2026 14:30:45] INFO [RAG] 🔍 Iniciando análisis de módulo: Matemáticas 101 | Data: {"module_id": 2, ...}
[16/Feb/2026 14:30:50] INFO [EMBEDDING] 📊 Embedding creado: Teorema de Pitágoras (dim: 384) | Data: {...}
[16/Feb/2026 14:32:10] INFO [DEEPSEEK] 🤖 Respuesta de DeepSeek (1234ms) | Data: {...}
```

## 🎓 Ejemplo Completo

### Flujo de Análisis de Módulo

1. **Usuario hace clic en "Analizar"**
   - POST `/api/analyze-module/2/`

2. **Events registrados:**
   ```json
   {
     "timestamp": "2026-02-16T14:30:45.123",
     "type": "RAG",
     "message": "🔍 Iniciando análisis de módulo: Matemáticas 101",
     "data": {"module_id": 2, "module_name": "Matemáticas 101", "action": "start"}
   }
   ```

3. **Por cada item en el módulo:**
   ```json
   {
     "timestamp": "2026-02-16T14:30:46.456",
     "type": "EMBEDDING",
     "message": "📊 Embedding creado: Teorema de Pitágoras (dim: 384)",
     "data": {"item_id": 45, "title": "Teorema de Pitágoras", "dimensions": 384}
   }
   ```

4. **Fin del análisis:**
   ```json
   {
     "timestamp": "2026-02-16T14:30:50.789",
     "type": "RAG",
     "message": "✅ Análisis completado - 8 items, 8 embeddings",
     "data": {"module_id": 2, "items": 8, "embeddings": 8, "action": "complete"}
   }
   ```

5. **Estadísticas actualizadas:**
   ```json
   {
     "rag": {
       "modules_analyzed": 1,
       "total_embeddings": 8,
       "last_analysis": "2026-02-16T14:30:50.789"
     }
   }
   ```

## 🎨 Dashboard - Guía Visual

El dashboard muestra:

```
┌─ Estadísticas RAG ─┬─ Estadísticas DeepSeek ─┬─ Eventos del Sistema ─┐
│ 5 Módulos         │ 12 Llamadas            │ 156 Eventos Total    │
│ 72 Embeddings     │ 4856 Tokens            │ 45 RAG               │
│ Última: hace 3min │ Tiempo prom: 2.3s      │ 12 DeepSeek          │
└───────────────────┴──────────────────────┴──────────────────┘

┌─ Eventos En Vivo (Filtros: Todos, RAG, DeepSeek, Errores) ─┬─ Base de Datos en Memoria ─┐
│ 14:32:10 🔍 Búsqueda RAG: "pregunta" → 3 resultados       │ 📚 module_2_course_1      │
│ 14:32:11 📊 Embedding creado: Concepto A (dim: 384)       │   📄 Documentos: 8        │
│ 14:32:12 🤖 Respuesta de DeepSeek (1.2s)                  │   📊 Embeddings: 8        │
│ 14:32:15 🔍 Búsqueda RAG: "otra pregunta" → 2 resultados  │                           │
│ 14:32:16 🤖 Respuesta de DeepSeek (1.5s)                  │ 📚 module_5_course_1      │
│ 14:32:20 📊 Embedding creado: Concepto B (dim: 384)       │   📄 Documentos: 12       │
│                                                             │   📊 Embeddings: 12       │
└──────────────────────────────────────────────────────────┴───────────────────────┘
```

## 🔧 Próximas Mejoras

Puedo agregar:
- [ ] Exportar eventos a CSV/JSON
- [ ] Gráficos de tendencias (tokens vs tiempo)
- [ ] Timeline visual de eventos
- [ ] Búsqueda avanzada de eventos
- [ ] Persistencia de eventos (guardar en archivo)
- [ ] Comparación de embeddings

## 📞 Preguntas Frecuentes

**P: ¿Dónde se guardan los eventos?**
R: En memoria (RAM) mientras la aplicación esté corriendo. Se pierden al reiniciar.

**P: ¿Esto ralentiza la aplicación?**
R: Mínimamente. Los logs se hacen en paralelo y en la mayoría de casos son microsegundos.

**P: ¿Puedo ver qué embeddings exactos se generaron?**
R: Sí, en el event log ves el ID, nombre y dimensiones de cada embedding. Los vetores reales están en ChromaDB/memoria.

**P: ¿Cómo sé si chromaDB está funcionando o usa fallback en memoria?**
R: En el dashboard ve "Base de datos en memoria" - si tiene colecciones, significa que está usando fallback.

---

**Ahora tienes visibilidad total en lo que sucede adentro del sistema. ¡Úsalo para entender, debuggear y optimizar!** 🚀
