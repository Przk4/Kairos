# INSTRUCCIONES URGENTES - Arregla tu Botón de Análisis

## Problema Identificado
El botón no deja re-analizar después de un análisis anterior. Esto es porque:
1. Los embeddings se pierden cuando reinicia el servidor (están en memoria)
2. El caché del navegador está sirviendo HTML viejo
3. Posiblemente hay conflicto con Canvas Auth token

## ⚡ FIX RÁPIDO - Sigue estos pasos EXACTAMENTE:

### Paso 1: Limpia el Caché
**IMPORTANTE:** No solo actualizar la página, sino limpiar TODO el caché

- **Windows:**
  - Presiona: `Ctrl + Shift + Del`
  - Selecciona: "Todas las cookies y otros datos del sitio"
  - Haz clic: "Borrar datos"
  
- **Mac:**
  - Abre DevTools: `Cmd + Shift + I`
  - Clic derecho en el botón refresh
  - Selecciona: "Vaciar caché e hacer recarga manual"

### Paso 2: Hard Refresh del Navegador
`Ctrl + F5` (Windows) o `Cmd + Shift + R` (Mac)

### Paso 3: Verifica que todo Funciona

**Opción A - Test Rápido (SIN autenticación necesaria):**
1. Abre: `http://127.0.0.1:8000/test-button/`
2. Haz clic en "Testear Servidor"
3. Haz clic en "Test Análisis"
4. Deberías ver "✓ Servidor responde correctamente"

**Opción B - Test Real (CON autenticación):**
1. Abre: `http://127.0.0.1:8000/`
2. Verifica que estés autenticado (si no, haz clic en "Conectar con Canvas")
3. Haz clic en cualquier botón "Analizar"
4. Espera a que se complete
5. El botón debería cambiar a "🔄 Re-analizar"
6. Deberías poder hacer clic de nuevo

---

## 🔍 Si Aún No Funciona - Debug en Consola

1. **Abre DevTools:** `F12`
2. **Ve a la pestaña "Console"**
3. **Haz clic en el botón "Analizar"**
4. **Copia y pégame TODO lo que aparece en la consola**

Eso me dirá exactamente qué está mal.

---

## ⚙️ Cambios que He Hecho

### 1. **Endpoint `/api/test-button-click/`** (NUEVO)
- Simula un análisis sin datos reales
- Para testear que los clics funcionan
- GET retorna info, POST simula análisis

### 2. **Página `/test-button/`** (NUEVA)
- Interfaz visual para testear
- Con console output integrada
- Verifica servidor, botón, y módulos

### 3. **Mejorado: Endpoint de Análisis**
- Más logging para debugging
- Mejor manejo de errores
- Mensajes claros en caso de fallo

### 4. **Mejorado: JavaScript del Botón**
- `console.log()` en cada paso
- SIEMPRE habilita el botón después (incluso si hay error)
- Mejor feedback visual

---

## 📝 Sobre el Problema de Canvas

Si a veces se desconecta:
1. Es porque el token Canvas expira
2. Solución temporal: Reconéctate a Canvas manualmente
3. Solución permanente (próxima fase): Implementar refresh automático de tokens

---

## 🚀 Quick Start - Ahora Mismo

```
1. Ctrl + F5 (limpiar caché)
2. Abre: http://127.0.0.1:8000/test-button/
3. Haz clic en "Testear Servidor"
4. Haz clic en "Test Análisis"
5. Deberías ver ✓ OK
```

Si TODO funciona en test pero NO en real:
→ Probablemente es un problema de Canvas Auth token

Si NADA funciona:
→ Abre DevTools (F12), Console, y reporta el error exacto

---

## 📞 Para Reportar Problemas

Necesito:
1. **Pantazo de la consola** (F12 → Console)
2. **Error exacto que sale**
3. **Módulo ID que intentas analizar** (ej: 1, 2, etc.)
4. **Browser que usas** (Chrome, Firefox, Edge, etc.)

Con eso 100% lo arreglo!

---

## ✅ Checklist

- [ ] Hice Ctrl+F5 para limpiar CACHÉ
- [ ] Abrí `/test-button/`
- [ ] Hice clic en "Testear Servidor" → ✓ OK
- [ ] Hice clic en "Test Análisis" → ✓ OK
- [ ] Si test OK pero real no funciona → Canvas Auth problema
- [ ] Si test NO funciona → Abre DevTools y reporta error

---

**Estado:** ✅ LISTO PARA TESTEAR
**Servidor:** Corriendo en `http://127.0.0.1:8000/`
**Test Page:** `http://127.0.0.1:8000/test-button/`
