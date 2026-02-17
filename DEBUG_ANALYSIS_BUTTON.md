# Debug Guide - Botón de Análisis No Funciona

## Paso 1: Limpiar Caché del Navegador

1. **Abre el Dashboard:** `http://127.0.0.1:8000/`
2. **Fuerza recarga de CACHÉ:**
   - Windows: `Ctrl + F5` o `Ctrl + Shift + Del`
   - Mac: `Cmd + Shift + R`
3. **Espera que cargue completamente**

---

## Paso 2: Abre la Consola del Navegador

1. Presiona `F12` para abrir DevTools
2. Ve a la pestaña **Console**
3. Verás mensajes cuando hagas clic en el botón

---

## Paso 3: Intenta Clickear el Botón

1. Haz clic en cualquier botón "Analizar"
2. Mira la consola - deberías ver:
   ```
   Analyze button clicked for module: 1
   Analysis response status: 200
   Analysis data: {status: 'completed', ...}
   Analysis completed successfully
   ```

---

## Si VES Errores en Consola

### Error 1: "Analyze button clicked for module: undefined"
**Problema:** El botón no tiene `data-module-id`
**Solución:** Limpia caché más agresivamente o reinicia server

### Error 2: "No estoy autenticado"
**Problema:** Canvas Auth expiró
**Solución:** Reconéctate a Canvas
**Código:** Status 401

### Error 3: "Módulo no encontrado"
**Problema:** El módulo ID no coincide
**Solución:** Verifica que el módulo existe en BD
**Código:** Status 404

### Error 4: "Token de Canvas expirado"
**Problema:** Canvas token no es válido
**Solución:** Reconéctate a Canvas y vuelve a intentar
**Código:** Status 401

---

## Si NO VES Nada en Consola

**Problema:** El JavaScript del botón no se está ejecutando

**Soluciones:**
1. Limpia caché de nuevo (Ctrl+F5)
2. Reinicia el navegador completamente
3. Abre en incognito: `Ctrl+Shift+N`
4. Contacta soporte

---

## Verificar que el Endpoint Funciona

En otra pestaña, abre DevTools y corre en consola:

```javascript
// Test endpoint
fetch('/api/module/1/analysis-status/')
  .then(r => r.json())
  .then(d => console.log('Status response:', d))
  .catch(e => console.error('Error:', e))
```

Deberías ver:
```json
{
  "status": "ok",
  "module_id": 1,
  "is_analyzed": false,
  "document_count": 0
}
```

---

## Si Todo Aparenta Funcionar pero No Analiza

1. **Abre DevTools (F12)**
2. **Ve a Network tab**
3. **Haz clic en "Analizar"**
4. **Busca request POST a `/api/analyze-module/1/`**
5. **Revisa la respuesta:**
   - Status 200 = OK
   - Status 401 = Auth problema
   - Status 404 = Module no existe

---

## Problema: "Desconexión de Canvas"

Si a veces desconecta Canvas auth:

1. Entra a `http://127.0.0.1:8000/logout`
2. Vuelve a `http://127.0.0.1:8000/login`
3. Reconéctate completamente
4. Espera 30 segundos
5. Intenta análisis de nuevo

Este problema es porque el token Canvas expira. Solución a largo plazo: implementar refresh automático de tokens.

---

## Checklist Rápido

- [ ] Hice Ctrl+F5 para limpiar caché
- [ ] Abrí DevTools (F12)
- [ ] Vu a Console tab
- [ ] Hice clic en botón "Analizar"
- [ ] Vi "Analyze button clicked" en consola
- [ ] La consola no muestra errores rojos
- [ ] El endpoint retorna datos JSON

Si todos los checks están OK, el análisis debería estar funcionando!

---

## Reportar Problema

Si aún no funciona, copia y pégame:

1. **Consola output** (full error message)
2. **Network tab response** (del POST request)
3. **Module ID** que intentas analizar
4. **Browser** que estás usando

Con eso puedo 100% arreglarlo!
