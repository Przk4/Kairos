# 🎓 Kairos AI - Sistema de Debugging y Monitoreo

Has solicitado **ver qué está pasando adentro** del sistema. He creado un ecosistema completo de debugging y configuración de IA.

---

## 📚 Tres Documentos Técnicos

He creado documentación técnica en la raíz del proyecto. LÉELOS EN ESTE ORDEN:

### 1️⃣ **EMBEDDINGS_GUIDE.md** 
**Lee primero esto** ← RECOMENDADO PARA EMPEZAR

- ¿Qué es un embedding? 
- ¿Qué son vectores?
- ¿Cómo funciona RAG?
- El flujo completo explicado
- Matemáticas detrás de similitud coseno
- Ejemplos con números reales

**Tiempo:** 15 minutos de lectura

---

### 2️⃣ **AI_PROVIDER_CONFIG.md**
**Lee esto después** ← Para entender la IA

- Cómo cambiar entre proveedores de IA
- Mock (hoy - gratis)
- DeepSeek (producción - pago)
- Hugging Face (intermedio - gratis)
- Plan de migración

**Tiempo:** 10 minutos de lectura

---

### 3️⃣ **DEBUG_GUIDE.md**
**Abre esto cuando necesites debugging** ← Para ver qué sucede

- Dashboard visual 
- APIs JSON para debug
- Cómo filtrar eventos
- Qué puedes ver en el sistema
- Casos de uso reales

**Tiempo:** 10 minutos de referencia

---

## 🎨 El Dashboard

**URL:** http://127.0.0.1:8000/debug/dashboard/

### Qué Ves:

```
┌─ Estadísticas RAG ─┬─ Estadísticas DeepSeek ─┬─ Eventos del Sistema ─┐
│ 5 Módulos         │ 12 Llamadas            │ 156 Eventos Total    │
│ 72 Embeddings     │ 4856 Tokens            │ 45 RAG               │
│ Última: hace 3min │ Tiempo prom: 2.3s      │ 12 DeepSeek          │
└───────────────────┴──────────────────────┴──────────────────┘

┌─ Eventos En Vivo ──────────────────────┬─ Base de Datos en Memoria ─┐
│ Filtros: Todos, RAG, DeepSeek, Error  │ 📚 module_2_course_1      │
│                                         │   Documentos: 8           │
│ 14:32:10 🔍 Búsqueda RAG              │   Embeddings: 8           │
│ 14:32:11 📊 Embedding creado           │                           │
│ 14:32:12 🤖 Respuesta DeepSeek        │ 📚 module_5_course_1      │
│                                         │   Documentos: 12          │
└─────────────────────────────────────┴───────────────────────┘

```

### Actualización en Tiempo Real
- Se actualiza cada 2 segundos
- Filtrable por tipo de evento
- Ver JSON detallado de cada evento

---

## ⚙️ Configuración: Sistema de IA

### HOY - Usar Mock (Gratis)
Abre: `tu_app/ai_service_config.py`

Busca línea ~241:
```python
ACTIVE_PROVIDER = "mock"
```

**Ventajas hoy:**
- ✅ Sin API key
- ✅ Sin costo
- ✅ Sin latencia
- ✅ Testing completo de lapp

---

### DESPUÉS - Cambiar a DeepSeek (Producción)

Cuando tengas dinero:

1. Obtén API key en https://platform.deepseek.com/
2. Agrega a `.env`:
   ```
   DEEPSEEK_API_KEY=sk_xxxxxx...
   ```
3. Cambia UNA línea en `tu_app/ai_service_config.py`:
   ```python
   ACTIVE_PROVIDER = "deepseek"
   ```
4. Reinicia Django

**¡Eso es todo!** Cero cambios en otros archivos.

---

## 📡 Las 4 APIs de Debugging

### 1. 🎨 Dashboard (Visual)
```
GET http://127.0.0.1:8000/debug/dashboard/
```
→ Una página bonita con todo

### 2. 📡 Eventos (JSON)
```
GET http://127.0.0.1:8000/api/debug/events/?type=RAG&limit=100
```
→ Lista de eventos en formato JSON

### 3. 📈 Estadísticas (JSON)
```
GET http://127.0.0.1:8000/api/debug/stats/
```
→ Números agregados del sistema

### 4. 📚 Documentos Analizados (JSON)
```
GET http://127.0.0.1:8000/api/debug/documents/?module_id=2
```
→ Qué items/documentos fueron analizados en cada módulo

---

## 🚀 Flujo de Ahora Mismo

```
1. Abre http://127.0.0.1:8000/
   → Conecta con Canvas (como antes)
   
2. Haz clic en "Analizar" un módulo
   → El sistema convierte archivos a vectores (embeddings)
   → Los guarda en memoria
   → Ve los eventos en el dashboard
   
3. Abre el dashboard: http://127.0.0.1:8000/debug/dashboard/
   → Ve qué documentos se analizaron
   → Ve los embeddings creados
   → Ve todas las estadísticas
   
4. Haz una pregunta en el chat
   → El sistema busca documento similares (RAG)
   → Envía la pregunta + contexto a Mock/DeepSeek/HF
   → Devuelve la respuesta
   → Todo se registra en el dashboard
```

---

## 📁 Archivos Nuevos (Explicación Rápida)

| Archivo | Propósito |
|---------|-----------|
| `tu_app/debug_service.py` | Servicio de logging/eventos |
| `tu_app/ai_service_config.py` | Sistema configurable de IA |
| `DEBUG_GUIDE.md` | Cómo usar el dashboard |
| `EMBEDDINGS_GUIDE.md` | Qué son embeddings |
| `AI_PROVIDER_CONFIG.md` | Cómo cambiar de IA |
| `tu_app/templates/tu_app/debug_dashboard.html` | Interface visual |
| `tu_app/views.py` (actualizado) | Nuevos endpoints de debug |
| `tu_app/urls.py` (actualizado) | Rutas del debug |
| `tu_app/rag_service.py` (actualizado) | Ahora loguea documentos |
| `tu_app/ai_service.py` (actualizado) | Ahora usa sistema configurable |

---

## 🎯 Casos de Uso

### "Quiero ver QUÉ documentos se analizaron"
1. Abre http://127.0.0.1:8000/debug/dashboard/
2. Busca la sección "Base de Datos en Memoria"
3. Ves cada módulo analizado con su lista de items
4. Versión JSON: GET `/api/debug/documents/`

### "Quiero ver QUÉ le pedía a la IA y qué me respondió"
1. Abre http://127.0.0.1:8000/debug/dashboard/
2. En "Eventos En Vivo", filtra por "DeepSeek"
3. Ve el prompt y la respuesta en el JSON de cada evento

### "Quiero entender cómo funcionan los vectores"
1. Lee **EMBEDDINGS_GUIDE.md** (está en raíz del proyecto)
2. Tiene explicación técnica + ejemplos matemáticos

### "Quiero cambiar a DeepSeek cuando tenga dinero"
1. Lee **AI_PROVIDER_CONFIG.md**
2. Obtén API key
3. Cambia una línea en `ai_service_config.py`

---

## 🔍 Qué Pasa Detrás de Escenas

**Cuando analizas un módulo:**
```
1. Cada documento → SentenceTransformer (embeddings local)
2. Se guarda: {documentos, vectores, metadata}
3. Se registra en debug_service
4. Ver en dashboard en tiempo real
```

**Cuando haces una pregunta:**
```
1. Pregunta → Convertir a vector (embedding)
2. Buscar documentos similares (búsqueda vectorial)
3. Recuperar top 3 documentos más similares
4. Enviar pregunta + contexto a IA (Mock/DeepSeek/HF)
5. Recibir respuesta
6. Registrar todo en debug_service
7. Ver en dashboard en tiempo real
```

---

## 📊 Ejemplo Real del Dashboard

Después de analizar un módulo y hacer una pregunta:

```
ESTADÍSTICAS RAG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Módulos Analizados: 1
Embeddings Total: 8
Última análisis: hace 2 minutos

ESTADÍSTICAS DEEPSEEK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Llamadas Totales: 1
Tokens Usados: 245
Tiempo Promedio: 1.2s

EVENTOS EN VIVO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
14:32:10 🔍 Iniciando análisis: Geometría
14:32:10 📊 Embedding: Punto y línea (384-dim)
14:32:10 📊 Embedding: Triángulos (384-dim)
14:32:10 📊 Embedding: Pitágoras (384-dim)
14:32:10 ✅ Análisis completado: 3 items
14:32:15 🔎 Búsqueda RAG: "¿hipotenusa?" → 3 resultados
14:32:16 🤖 Respuesta DeepSeek (1.2s) - 245 tokens

BASE DE DATOS EN MEMORIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 module_2_course_1
   Documentos: 3
   Embeddings: 3
   Actualizado: hace 5 minutos
```

---

## ✅ Resumen Rápido

| Pregunta | Respuesta | Dónde |
|----------|-----------|-------|
| **¿Qué son embeddings?** | Números que representan significado | EMBEDDINGS_GUIDE.md |
| **¿Cómo veo qué se guardó?** | Dashboard o `/api/debug/documents/` | debug/dashboard/ |
| **¿Cómo cambio a DeepSeek?** | Una línea en `ai_service_config.py` | AI_PROVIDER_CONFIG.md |
| **¿Qué está pasando ahora?** | Abre el dashboard y ve eventos en vivo | debug/dashboard/ |
| **¿Cómo funciona el RAG?** | Búsqueda vectorial + IA | EMBEDDINGS_GUIDE.md |

---

## 🎓 Próximos Pasos

### Hoy (5 minutos)
- [ ] Lee EMBEDDINGS_GUIDE.md (para entender vectores)
- [ ] Abre http://127.0.0.1:8000/debug/dashboard/
- [ ] Analiza un módulo y observa

### Mañana (10 minutos)
- [ ] Lee AI_PROVIDER_CONFIG.md
- [ ] Considera Hugging Face como alternativa gratis
- [ ] Plan para cambiar a DeepSeek cuando tengas presupuesto

### La Próxima Semana
- [ ] Obtén dinero ($10) para DeepSeek
- [ ] Cambia a DeepSeek (es sólo una línea)
- [ ] Disfruta de IA profesional

---

## 🎯 Meta: Visibilidad Total

Ahora tienes:
- ✅ Ver qué documentos se analizan
- ✅ Ver qué embeddings se crean
- ✅ Ver qué entra/sale de la IA
- ✅ Ver estadísticas en tiempo real
- ✅ Sistema de IA flexible (cambiar sin romper código)
- ✅ Testing gratis hoy, producción después

**¡Bienvenido a la arquitectura moderna de IA! 🚀**

---

## 📞 ¿Preguntas?

- Técnicas sobre vectores → Ver EMBEDDINGS_GUIDE.md
- Cómo cambiar IA → Ver AI_PROVIDER_CONFIG.md
- Cómo usar dashboard → Ver DEBUG_GUIDE.md

¡Que disfrutes debugging! 🎉
