# 🔧 Guía de Configuración: Sistema de IA Configurable

## ¿Por qué esto es genial?

Hoy usas **Mock** (gratuito, sin API):
- ✅ Sin costos
- ✅ Funciona inmediatamente
- ✅ Prueba la app completa
- ✅ No necesita credenciales

Mañana cambias a **DeepSeek** (producción):
- ✅ Una línea de código
- ✅ Cero cambios en el resto
- ✅ Directamente en producción

---

## 📍 Dónde Está la Magia

**Archivo:** `tu_app/ai_service_config.py`

Línea clave:
```python
# 👇 CAMBIAR AQUÍ PARA USAR UN PROVEEDOR DIFERENTE 👇
ACTIVE_PROVIDER = "mock"  # "deepseek", "huggingface", o "mock"
```

---

## 🚀 Cómo Cambiar de Proveedor

### HOY: Usar Mock (Gratis, sin API)

```python
ACTIVE_PROVIDER = "mock"
```

**Características:**
- Responde automáticamente sin conectar a ningún lado
- Perfecto para testing
- Respuestas sensatas basadas en palabras clave

**Ventajas:**
```
✅ Sin costo
✅ Sin latencia
✅ Sin API key requerida
✅ Funciona offline
❌ Respuestas sintéticas (no inteligentes)
```

---

### DESPUÉS: Usar DeepSeek (Producción)

1. **Obtén API key en deepseek.com**
   - Abre https://platform.deepseek.com/
   - Crea una cuenta
   - Obtén tu API key
   - Agrega crédito ($5-10 suficiente para testing)

2. **Configura en `.env`:**
   ```
   DEEPSEEK_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. **Cambia una línea en `ai_service_config.py`:**
   ```python
   ACTIVE_PROVIDER = "deepseek"
   ```

4. **Reinicia el servidor:**
   ```bash
   python manage.py runserver
   ```

5. **¡Listo!** El sistema automáticamente usará DeepSeek. Sin otros cambios.

---

### ALTERNATIVA: Usar Hugging Face (Gratis, requiere API key)

Si no quieres pagar a DeepSeek ahora:

1. **Obtén API key gratis en huggingface.co:**
   - Abre https://huggingface.co/
   - Crea una cuenta gratis
   - Ve a Settings → Access Tokens
   - Crea un nuevo token (read-only está bien)

2. **Configura en `.env`:**
   ```
   HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxxxxxxxxx
   ```

3. **Cambia en `ai_service_config.py`:**
   ```python
   ACTIVE_PROVIDER = "huggingface"
   ```

4. **Reinicia el servidor**

**Ventajas:**
```
✅ Completamente gratis
✅ Respuestas inteligentes reales
✅ No necesita dinero
❌ Más lento (1-3 segundos por respuesta)
❌ Limitado a cierto número de llamadas/mes (gratuito)
```

---

## 📊 Comparación de Proveedores

| Aspecto | Mock | Hugging Face | DeepSeek |
|---------|------|--------------|----------|
| **Costo** | Gratis | Gratis | Pago (~$0.001/1K tokens) |
| **Calidad** | Low (reglas) | Medium (IA real) | High (IA avanzada) |
| **Velocidad** | Instant | Lenta (1-3s) | Rápida (0.5-1s) |
| **API Key** | No | Sí | Sí |
| **Uso** | Testing | Desarrollo | Producción |

---

## 🔄 El Cambio es Así de Fácil

```python
# Archivo: tu_app/ai_service_config.py
# Línea: 241

# HOY (cambio minimal de código)
ACTIVE_PROVIDER = "mock"

# MAÑANA (una sola línea cambia)
ACTIVE_PROVIDER = "deepseek"

# ¿Qué cambió en otros archivos?
# NADA. Cero cambios. El sistema es inteligente.
```

---

## 📈 Cómo Se Usa Internamente

```
Pregunta del estudiante
    ↓
views.py llama: ai = get_ai_service()
    ↓
ai_service.py délega a: get_ai_service()
    ↓
ai_service_config.py retorna el proveedor configurado
    ↓
Se ejecuta el método correcto:
  - Si es "mock" → MockAIProvider.answer_question()
  - Si es "deepseek" → DeepSeekProvider.answer_question()
  - Si es "huggingface" → HuggingFaceProvider.answer_question()
```

---

## 💡 Hoy: Testing Completo sin Dinero

```python
# Hoy: usa Mock
ACTIVE_PROVIDER = "mock"

# Puedo:
✅ Analizar módulos
✅ Crear embeddings
✅ Hacer preguntas al chat
✅ Ver respuestas
✅ Testing completo de la app
✅ Sin gastar nada
```

---

## 🎯 Plan Recomendado

### Semana 1: Development (Mock)
```python
ACTIVE_PROVIDER = "mock"
```
- Desarrolla la app
- Prueba features
- Sin costo

### Semana 2-3: Testing Avanzado (Hugging Face Gratis)
```python
ACTIVE_PROVIDER = "huggingface"
```
- IA real sin costo
- Prueba con respuestas inteligentes
- Preparar para producción

### Producción: DeepSeek
```python
ACTIVE_PROVIDER = "deepseek"
```
- IA de mejor calidad
- Respuestas más rápidas
- Costo mínimo (~$0.001 por pregunta)

---

## 🔍 Ver Qué Proveedor Está Activo

**En los logs del servidor:**
```
INFO 🤖 Sistema de IA configurado para usar: MOCK
```

o

```
INFO ✅ DeepSeek Provider inicializado
```

o

```
INFO ✅ Hugging Face Provider inicializado
```

---

## 📋 Checklist de Cambio

Si cambias a un nuevo proveedor:

- [ ] Obtener API key (si es requerido)
- [ ] Agregar API key a `.env`
- [ ] Cambiar `ACTIVE_PROVIDER` en `ai_service_config.py`
- [ ] Guardar archivo
- [ ] Reiniciar servidor Django
- [ ] Hacer una prueba (pregunta en chat)
- [ ] Ver logs para confirmar

---

## ⚠️ Nota Importante

**NO debes:**
- ❌ Cambiar múltiples archivos
- ❌ Modificar imports
- ❌ Tocar vistas o URLs
- ❌ Actualizar base de datos

**SÍ haces:**
- ✅ Una línea en `ai_service_config.py`
- ✅ Agregar API key a `.env` (si es requerido)
- ✅ Reiniciar server

---

## 🐛 Troubleshooting

**P: Cambié a DeepSeek pero sigue usando Mock**
R: Reinicia el servidor. Los imports se cachean en Python.

**P: DeepSeek dice "Invalid API key"**
R: Verifica que la key en `.env` sea correcta. Cópiala nuevamente de deepseek.com

**P: Hugging Face es muy lento**
R: Es normal. El servidor gratuito es lento. Usa DeepSeek en producción.

**P: ¿Cuánto cuesta DeepSeek?**
R: Aproximadamente $0.0005-0.002 por pregunta, dependiendo de la complejidad.

---

## 🎓 Conclusión

Este diseño te permite:
1. **Desarrollar hoy** sin gastar dinero (Mock)
2. **Probar mañana** con IA real (Hugging Face)
3. **Producir después** con la mejor IA (DeepSeek)

**Y todo con UN SOLO CAMBIO DE LÍNEA.**

¡Así es como se hace arquitectura flexible! 🚀
