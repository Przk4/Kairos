# 📊 Guía Técnica: Embeddings, Vectores y RAG

## ¿Qué es un Embedding?

Un **embedding** es una representación numérica de un documento (texto, palabra, imagen, etc.) en forma de **vector de números reales**.

```
Documento:  "El teorema de Pitágoras: a² + b² = c²"
                        ↓ (SentenceTransformer)
Embedding:  [0.234, -0.567, 0.891, -0.123, 0.456, ..., 0.789]
            ^                                              ^
            Inicio del vector                       Fin del vector
            (384 dimensiones en nuestro caso)
```

### ¿Cómo funciona la magia?

El modelo `sentence-transformers/all-MiniLM-L6-v2` es una **red neuronal pre-entrenada** que:

1. **Lee el texto** y lo procesa
2. **Transforma el significado** en números
3. **Genera 384 números** que capturan la "esencia" del texto

**Ejemplo real:**
```
"a² + b² = c²"            → [0.23, -0.45, 0.67, ... ] (384 números)
"Pitágoras"               → [0.25, -0.43, 0.68, ... ] (384 números)
"Ley de cosenos"          → [0.24, -0.44, 0.66, ... ] (384 números)

"Cómo cocinar pasta"      → [0.91, -0.12, 0.34, ... ] (384 números)
                               ↑ Muy diferente!
```

Matemáticamente, podemos **medir la similitud** entre dos documentos:

```
Similitud = (Vector1 · Vector2) / (||Vector1|| × ||Vector2||)
            ↑ Producto punto
```

**Resultado:** Un número entre -1 y 1
- **1.0** = Idénticos
- **0.5** = Similares
- **0.1** = Algo similares
- **0.0** = Completamente diferentes

---

## El Flujo RAG Completo

```
Pregunta del Estudiante
│
├─→ [1. EMBEDDING] Convertir pregunta a vector
│   "¿Cómo uso Pitágoras?"
│                  ↓
│   [0.23, -0.45, 0.67, ... ] (384 números)
│
├─→ [2. BÚSQUEDA VECTORIAL] Comparar con documentos guardados
│   Documento A: [0.234, -0.567, 0.891, ... ]  → Similitud: 0.87 ✅
│   Documento B: [0.456, -0.123, 0.789, ... ]  → Similitud: 0.45
│   Documento C: [0.891, -0.234, 0.456, ... ]  → Similitud: 0.23
│
├─→ [3. RECOPILACIÓN DE CONTEXTO] Tomar los 3 más similares
│   Contexto = [
│     { contenido: "Teorema de Pitágoras...", similitud: 0.87 },
│     { contenido: "Aplicaciones del...", similitud: 0.45 },
│     { contenido: "Historia de Pitágoras...", similitud: 0.23 }
│   ]
│
└─→ [4. RESPUESTA DE IA] Enviar pregunta + contexto a DeepSeek
    Prompt: """
    Contexto:
    - Teorema de Pitágoras es...
    - Aplicaciones en...
    
    Pregunta: ¿Cómo uso Pitágoras?
    
    Responde en base al contexto.
    """
    
    DeepSeek genera:
    "El Teorema de Pitágoras se usa en triángulos...
     En tu caso puedes aplicarlo cuando..."
```

---

## ¿Qué Está Pasando en Kairos?

### Fase 1: ANÁLISIS DE MÓDULO
Cuando haces clic en "Analizar":

```
Módulo: "Geometría Básica"
├─ Item 1: "Punto y línea" 
│  ├─ Texto: "Un punto es..."
│  └─ Embedding: [0.123, -0.456, 0.789, ..., 0.321]  ✅ GUARDADO
│
├─ Item 2: "Triángulos"
│  ├─ Texto: "Un triángulo tiene 3 ángulos..."
│  └─ Embedding: [0.234, -0.567, 0.891, ..., 0.432]  ✅ GUARDADO
│
├─ Item 3: "Teorema de Pitágoras"
│  ├─ Texto: "a² + b² = c² donde..."
│  └─ Embedding: [0.345, -0.678, 0.901, ..., 0.543]  ✅ GUARDADO
│
└─ Item N: ...
   └─ Embedding: [0.456, -0.789, 0.012, ..., 0.654]  ✅ GUARDADO
```

**En el dashboard ves:**
- ✅ "Módulo: 3 items, 3 embeddings"
- La colección en memoria está llena de vectores

### Fase 2: PREGUNTA DE ESTUDIANTE
Estudiante pregunta: *"¿Cuándo uso Pitágoras?"*

```
1. Convertir pregunta:
   "¿Cuándo uso Pitágoras?" 
   → [0.340, -0.670, 0.890, ..., 0.540]  (384 números)

2. Comparar con cada embedding guardado:
   
   vs Item 1 "Punto y línea":        Similitud = 0.12 (bajo)
   vs Item 2 "Triángulos":            Similitud = 0.34 (medio)
   vs Item 3 "Teorema de Pitágoras":  Similitud = 0.89 (MUY ALTO) ✅
   
3. Tomar los TOP 3:
   1. "Teorema de Pitágoras..."  (0.89)
   2. "Triángulos..."             (0.34)
   3. "Punto y línea..."          (0.12)

4. Enviar a DeepSeek con contexto:
   Contexto: [documento 1, 2, 3]
   + Pregunta: "¿Cuándo uso Pitágoras?"
   = Respuesta inteligente basada en el currículo
```

---

## Los dos "Cerebros" de Kairos

### 🧠 Cerebro 1: EMBEDDING (sentence-transformers)
**Función:** Entender significado
- **Gratuito:** ✅ (open source)
- **Local:** ✅ (se ejecuta en tu PC)
- **Rápido:** ✅ (milisegundos)
- **Modelo:** `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensiones:** 384 números por documento

**¿Qué hace bien?**
- Detectar si dos textos hablan del mismo tema
- Encontrar documentos similares a una pregunta
- Es eficiente y no necesita internet

### 🤖 Cerebro 2: IA GENERATIVA (DeepSeek / alternativa gratuita)
**Función:** Generar respuestas
- **DeepSeek:** 💰 API pago
- **Alternativa (hoy):** Gratis
- **Cambiar después:** 1 línea de código
- **Calidad:** Ambas generan texto coherente

---

## ¿Cómo los Vectores se Guardan?

### Opción A: ChromaDB (base de datos vectorial)
```python
collection.add(
    ids=["item_45"],
    embeddings=[[0.123, -0.456, 0.789, ...]],  # Vector
    documents=["El texto original"],            # Referencia
    metadatas=[{"item_id": 45}]                 # Info extra
)
```

**ChromaDB es un gestor experto en:**
- Guardar vectores eficientemente
- Buscar el documento más similar en milisegundos
- Escalar a millones de documentos

### Opción B: Base de Datos en Memoria (fallback)
```python
in_memory_db["module_2_course_1"] = {
    'documents': ["texto 1", "texto 2", ...],
    'embeddings': [[0.123, ...], [0.456, ...], ...],
    'metadatas': [{"id": 1}, {"id": 2}, ...]
}
```

**Sin ChromaDB:**
- Más lento (busca lineal)
- Menos escalable
- Pero funciona perfectamente para desarrollo

---

## Las Matemáticas de Similitud Coseno

Es la fórmula que usamos para encontrar documentos similares:

```
         Vector A · Vector B
Cos(θ) = ─────────────────────
         ||Vector A|| × ||Vector B||

Donde:
• Vector A · Vector B = suma de (elemento_i × elemento_i) para cada dimensión
• ||Vector A|| = raíz cuadrada de la suma de cuadrados de elementos
```

**Ejemplo simple (2 dimensiones):**
```
Documento 1: [3, 4]
Documento 2: [6, 8]

Producto punto = (3×6) + (4×8) = 18 + 32 = 50
||Doc 1|| = √(3² + 4²) = √25 = 5
||Doc 2|| = √(6² + 8²) = √100 = 10

Similitud = 50 / (5 × 10) = 50 / 50 = 1.0 = IDÉNTICOS
```

Con **384 dimensiones:**
```
Producto punto = a₁b₁ + a₂b₂ + ... + a₃₈₄b₃₈₄
||A|| = √(a₁² + a₂² + ... + a₃₈₄²)
||B|| = √(b₁² + b₂² + ... + b₃₈₄²)
```

El resultado sigue siendo un número entre -1 y 1.

---

## 🔬 Caso de Uso Real: Matemáticas

```
MÓDULO: Geometría (3 documentos guardados)

Doc 1: "Triángulo rectángulo con catetos 3 y 4"
Embedding: [0.125, -0.234, 0.567, ...] (384 números)

Doc 2: "Hipotenusa se calcula con a² + b²"
Embedding: [0.128, -0.231, 0.569, ...] (384 números)

Doc 3: "Los ángulos internos suman 180°"
Embedding: [0.812, -0.456, 0.123, ...] (384 números)

────────────────────────────────────────

PREGUNTA: "¿Cuál es la hipotenusa de un triángulo con lados 3 y 4?"

Convertir pregunta: [0.126, -0.233, 0.568, ...] (384 números)

BÚSQUEDA:
vs Doc 1: similitud = 0.98 ✅✅✅ (Similar!)
vs Doc 2: similitud = 0.96 ✅✅✅ (Muy similar!)
vs Doc 3: similitud = 0.12 ❌ (Diferentes temas)

CONTEXTO ENVIADO A IA:
"
Contexto del curso:
1. Triángulo rectángulo con catetos 3 y 4
2. Hipotenusa se calcula con a² + b²
3. Los ángulos internos suman 180°

Pregunta: ¿Cuál es la hipotenusa de un triángulo con lados 3 y 4?
"

RESPUESTA DE IA:
"Usando la fórmula de Pitágoras (a² + b² = c²):
c² = 3² + 4² = 9 + 16 = 25
c = 5

Por lo tanto, la hipotenusa es 5."
```

---

## 💾 Qué Se Almacena en el Dashboard

Cuando haces clic en "Analizar", en el dashboard (Fase 2: próxima versión mejorada) verás:

```
MÓDULO: "Geometría Básica"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 Item 1: "Punto y línea"
   Tipo: Página
   Texto: "Un punto es..."
   Embedding: 384-dimensional ✅
   
📄 Item 2: "Triángulos"  
   Tipo: Página
   Texto: "Un triángulo tiene 3 lados..."
   Embedding: 384-dimensional ✅
   
📄 Item 3: "Teorema de Pitágoras"
   Tipo: Archivo PDF
   Texto: "El teorema de Pitágoras establece..."
   Embedding: 384-dimensional ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 3 Items | 3 Embeddings | Memoria: ~50KB
```

---

## 🎓 Comparación: Búsqueda Tradicional vs. RAG

### Búsqueda Tradicional (Keyword)
```
Pregunta: "Pitágoras"
Base de datos: SELECT * FROM items WHERE content LIKE "%Pitágoras%"

Problema: "¿Cómo se calcula la hipotenusa?" 
→ No encuentra documentos que no contengan "Pitágoras" o "hipotenusa"
→ Pierde documentos relevantes
```

### Búsqueda Vectorial (RAG)
```
Pregunta: "¿Cómo se calcula la hipotenusa?"
Embedding: [0.126, -0.233, 0.568, ...]

Comparar similitud cosmética contra TODOS los embeddings guardados:
→ Encuentra "Teorema de Pitágoras" (similar semánticamente)
→ Encuentra "Triángulo rectángulo" (contexto relevante)
→ Ignora "Los ángulos suman 180°" (menos relevante)

✅ Entiende SIGNIFICADO, no solo palabras clave
```

---

## 🚀 Stack Técnico Kairos

```
┌─────────────────────────────────────────────────┐
│ Interfaz de Usuario                             │
│ (HTML/JS - Dashboard + Chat)                    │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ API Django (REST)                               │
│ /api/analyze-module/ | /api/chat/               │
└────────────────┬────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼──────────────┐  ┌───────▼──────────────┐
│ RAG Service      │  │ AI Service           │
│ (rag_service.py) │  │ (ai_service.py)      │
│                  │  │                      │
│ 1. Embeddings    │  │ 1. Procesa Q+ctx    │
│    (ortransformers)│ │ 2. Llama DeepSeek   │
│ 2. Búsqueda      │  │ 3. Devuelve respuesta│
│    vectorial     │  │                      │
│ 3. Recuperación  │  │                      │
│    de contexto   │  │                      │
└───┬──────────────┘  └───────┬──────────────┘
    │                         │
    ▼                         ▼
┌─────────────────┐  ┌──────────────────────┐
│ ChromaDB /      │  │ DeepSeek API         │
│ Memory Storage  │  │ (https://deepseek..)│
│ (Base de datos  │  │                      │
│ vectorial)      │  │ o alternativa gratis │
└─────────────────┘  └──────────────────────┘
```

---

## 📊 Visualización: Qué Pasa en Tiempo Real

Cuando el dashboard se actualiza:

```
EVENTO         | TIMESTAMP      | DETALLES
───────────────┼────────────────┼──────────────────────────
RAG: Inicio    | 14:32:10.123   | Analizando "Geometría" 
EMBEDDING      | 14:32:10.234   | Punto y línea (384-dim)
EMBEDDING      | 14:32:10.345   | Triángulos (384-dim)
EMBEDDING      | 14:32:10.456   | Pitágoras (384-dim)
RAG: Fin       | 14:32:10.567   | 3 items, 3 embeddings ✅
RAG: Búsqueda  | 14:32:15.123   | ¿Hipotenusa? → 3 resultados
DEEPSEEK       | 14:32:16.234   | Respuesta generada (1.2s)
───────────────┴────────────────┴──────────────────────────
```

---

## 🎯 Takeaway

**Lo importante que debes saber:**

1. **Embedding** = Documentos convertidos a números (384 de ellos)
2. **Similitud coseno** = Comparar vectores para encontrar documentos parecidos
3. **RAG** = Usar documentos similares como contexto para la IA
4. **ChromaDB** = Base de datos experta en búsqueda vectorial
5. **DeepSeek** = IA que genera respuestas basadas en contexto

**En tu caso:**
- Los **embeddings son gratis** (sentence-transformers local)
- **La IA es lo que cuesta** (DeepSeek API)
- Hoy usas una IA gratis para testing
- Cambiar a DeepSeek después = 1-2 líneas de código

¿Preguntas sobre las matemáticas o el flujo?
