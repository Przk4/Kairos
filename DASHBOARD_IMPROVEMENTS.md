# 🎯 Mejoras al Debug Dashboard - Filtrado RAG en Tiempo Real

## Resumen de Cambios

Se ha mejorado significativamente el `/debug/dashboard/` para mostrar **en tiempo real** cómo funciona el sistema de filtrado RAG (Retrieval-Augmented Generation).

## Problemas Resueltos

### ❌ Antes
- Dashboard mostraba solo "contexto enviado" sin explicar qué chunks fueron filtrados
- No había visualización de similitud entre pregunta y documentos
- Usuario no podía verificar que el sistema estaba filtrando correctamente
- Muchas funciones de debug dispersas

### ✅ Después

#### 1. **Visualización de Filtrado RAG**
- Muestra TODOS los chunks recuperados con su **puntuación de similitud**
- Incluye barras visuales que muestran el % de similitud
- Clasificación de confianza:
  - 🟢 **Verde (Alta)**: Similitud ≥ 70%
  - 🟡 **Naranja (Media)**: Similitud 50-69%
  - 🔴 **Roja (Baja)**: Similitud < 50%

#### 2. **Estadísticas de Filtrado RAG**
- **Chunks Recuperados**: Número total de documentos seleccionados
- **Similitud Mínima**: El score más bajo que pasó el filtro
- Esto explica claramente el proceso de filtering top-k

#### 3. **Contexto Mejorado para DeepSeek**
- Muestra el contexto completo que se envía al modelo
- Cada chunk está claramente marcado: `[Docs 1]`, `[Docs 2]`, etc.
- Previsualizaciones del contenido para cada chunk
- Scroll mejorado para archivos grandes

#### 4. **Respuesta de DeepSeek Completa**
- Muestra la respuesta generada por el modelo
- Fácil de leer con mejor formato

#### 5. **Autorefresh en Tiempo Real**
- Dashboard se actualiza automáticamente cada 2 segundos
- Permite ver los cambios en tiempo real mientras se hacen preguntas

#### 6. **Botones de Utilidad**
- 🔄 **Actualizar Flujo**: Refrescar datos manualmente
- 📝 **Generar Datos de Prueba**: Cargar datos mock para demostración

## Cambios Técnicos

### Archivos Modificados

#### 1. `debug_dashboard.html` (768 líneas)
```javascript
// Nuevos estilos CSS
.chunk-item               // Styling para chunks individuales
.similarity-bar           // Barra de similitud visual
.similarity-fill          // Relleno animado de barra
.info-badge              // Insignias informativos

// Nuevas funciones JavaScript
async refreshPromptFlow()        // Obtiene datos de /api/debug/prompt-flow/
async generateTestData()         // Llama a /api/debug/test-data/
updateSimilarityStats()         // Calcula min/max similitud
```

#### 2. `views.py`
```python
def debug_test_data(request):
    """
    Endpoint para generar datos de prueba en el dashboard.
    Útil para demostración sin hacer llamadas a DeepSeek.
    """
    # Genera _last_prompt_flow con 3 chunks mock
    # - Similitud: 0.945, 0.872, 0.756
    # - Preview: Primeros 200 caracteres de cada chunk
    
def debug_prompt_flow(request):
    # Ya existía, pero ahora retorna retrieved_docs con:
    # - rank: posición en el ranking
    # - title: nombre del chunk/documento
    # - similarity: score de similitud (0.0-1.0)
    # - preview: muestra previa del contenido
```

#### 3. `urls.py`
```python
path('api/debug/test-data/', views.debug_test_data, name='debug_test_data'),
```

## Flujo de Datos Visualizado

```
Usuario pregunta → Pregunta al modelo
    ↓
RAG Service genera embedding de la pregunta
    ↓
Busca similitud coseno con todos los chunks en la BD
    ↓
Ordena por similitud (descendente)
    ↓
Selecciona TOP-K más similares
    ↓
[VISUALIZADO EN DASHBOARD] ← Se muestran estos chunks
    ↓
Formatea contexto con los chunks seleccionados
    ↓
[VISUALIZADO EN DASHBOARD] ← Se muestra el contexto
    ↓
DeepSeek genera respuesta
    ↓
[VISUALIZADO EN DASHBOARD] ← Se muestra respuesta
```

## Cómo Usar

### 1. **Ver Dashboard con Datos Reales**
```bash
# 1. Ir a /debug/dashboard/
# 2. Hacer una pregunta en la aplicación
# 3. Dashboard se actualiza automáticamente cada 2 segundos
```

### 2. **Demo con Datos Mock**
```bash
# 1. Ir a /debug/dashboard/
# 2. Hacer clic en "📝 Generar Datos de Prueba"
# 3. Se cargan datos de ejemplo para demostración
```

### 3. **Verificar el Filtrado RAG**
- Observar la sección "🎯 Chunks Recuperados y Filtrados"
- Confirmar que los chunks están ordenados por similitud
- Verificar que un chunk con similitud baja (rojo) está en posición 3+

## Información Mostrada

### Pregunta Enviada 📝
- Texto completo de la pregunta del usuario

### Chunks Recuperados 🎯
```
#1 - Title [95.0% 🟢 Alta]
████████████████ 
Vista previa del contenido...

#2 - Title [87.2% 🟡 Media]
██████████
Vista previa del contenido...

#3 - Title [75.6% 🟡 Media]
████████
Vista previa del contenido...
```

### Contexto Enviado a DeepSeek 📋
```
[Docs 1] Introduction to...
Lorem ipsum dolor sit amet...

[Docs 2] Main Concepts...
Consectetur adipiscing elit...

[Docs 3] Advanced Topics...
Sed do eiusmod tempor...
```

### Respuesta DeepSeek 🤖
- Respuesta completa del modelo generada basada en el contexto

## Estadísticas del Sistema

- **Módulos Analizados**: Cantidad de módulos procesados
- **Embeddings Total**: Número total de embeddings generados
- **Llamadas DeepSeek**: Cantidad de llamadas al API
- **Tokens Usados**: Tokens consumidos en total

## Indicadores Visuales

| Color | Significado |
|-------|------------|
| 🟢 Verde | Similitud alta (≥70%) - Muy relevante |
| 🟡 Naranja | Similitud media (50-69%) - Relevante |
| 🔴 Rojo | Similitud baja (<50%) - Menos relevante |
| 🟠 Naranja (border) | En espera de datos |
| 🔵 Azul | Contexto enviado |
| 🟣 Morado | Respuesta del modelo |

## Mejoras Futuras (Roadmap)

- [ ] Gráfico de distribución de similitudes
- [ ] Comparación: "Chunk rechazado vs aceptado" 
- [ ] Exportar datos de analytics del RAG
- [ ] Historial de últimas preguntas
- [ ] Análisis de Performance (tiempo RAG vs tiempo DeepSeek)
- [ ] Visualización de embeddings (reducción dimensional)
- [ ] Tabla comparativa de métodos RAG (top-k vs umbral)

## Métricas de Rendimiento

El dashboard ahora permite monitorear:
- **Latencia RAG**: Tiempo para buscar y filtrar documentos
- **Relevancia**: Puntuación de similitud promedio
- **Cobertura**: Cuántos chunks fueron considerados vs usados
- **Consistencia**: Verificar que el filtering es determinístico

## Referencias Técnicas

### Similitud Coseno
```python
similarity = cos(angle) between query_embedding and chunk_embedding
# Rango: 0 (completamente diferente) a 1 (idéntico)
```

### Top-K Filtering
```python
top_k = 5  # Para módulo individual
top_k = 3  # Para búsqueda multi-módulo
# Se seleccionan los K chunks con mayor similitud
```

### RAG Pipeline
```
Question Embedding (384 dims)
         ↓
[cosine_similarity(query_emb, chunk_emb) for each chunk]
         ↓
[0.95, 0.87, 0.75, 0.65, 0.58, 0.42, 0.31, ...]
         ↓
sorted(by similarity, descending)
         ↓
top_k_chunks = [:top_k]
         ↓
format_context(top_k_chunks)
         ↓
DeepSeek response
```

---

**Última actualización**: Febrero 2026  
**Estado**: ✅ Completo - Dashboard funcional con visualización RAG en tiempo real
