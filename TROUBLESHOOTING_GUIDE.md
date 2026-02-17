# Troubleshooting Guide - State Synchronization

## Common Issues & Solutions

### Issue 1: Button Still Shows Wrong State After Refresh

**Symptoms:**
- Open http://127.0.0.1:8000/
- Button shows "✅ Analizado" but should show "🔍 Analizar"
- Refresh page → Still wrong

**Diagnosis:**
```
1. Open DevTools (F12)
2. Go to Console tab
3. Check for JavaScript errors
4. Look for: "Error in syncModuleAnalysisStatus"
```

**Debug Steps:**

**Step 1: Check if endpoint is reachable**
```bash
# Terminal: Test the endpoint directly
curl http://127.0.0.1:8000/api/module/2/analysis-status/

# Expected response:
{"status": "ok", "is_analyzed": true, "document_count": 5, ...}
```

**Step 2: Check browser console for errors**
```javascript
// In browser console (F12 → Console)
// Look for fetch errors:
TypeError: Failed to fetch
404: Not Found
Unexpected token < in JSON at position 0  // (HTML error page)
```

**Step 3: Verify Django server is running**
```bash
# Check if server is running and has new code
# Try accessing: http://127.0.0.1:8000/api/debug/events/
# Should return JSON, not 404

# If 404, restart Django:
python manage.py runserver 127.0.0.1:8000
```

**Step 4: Check browser's Network tab**
```
1. Open DevTools (F12)
2. Go to Network tab
3. Refresh page
4. Look for: api/module/...../analysis-status/
5. Check response status (200 = good, 404 = endpoint missing)
6. Click request → see Response tab
```

**Solutions:**

| Symptom | Solution |
|---------|----------|
| **Endpoint returns 404** | Restart Django with `python manage.py runserver` |
| **Endpoint returns 500** | Check Django console for errors |
| **Response is HTML (error page)** | 404 or server error - restart Django |
| **Console shows fetch error** | Check URL format: `/api/module/NUM/analysis-status/` |

---

### Issue 2: Analysis Button Disabled, Can't Click

**Symptoms:**
- Button shows "✅ Analizado" and is disabled
- Want to re-analyze but can't click
- Button text doesn't change

**Diagnosis:**
```
Question: Is the module actually analyzed?
- YES → Button correctly disabled (expected)
- NO  → Button state wrong, needs sync
```

**Debug Steps:**

**Step 1: Check actual backend state**
```bash
# Check if embeddings exist
curl http://127.0.0.1:8000/api/debug/documents/?module_id=2

# If response is empty [], embeddings are gone
# But button still shows ✅ → STALE STATE
```

**Step 2: Force button state reset**
```javascript
// In browser console:
// Manually call sync for module ID 2
fetch('/api/module/2/analysis-status/')
    .then(r => r.json())
    .then(data => console.log(data));

// If is_analyzed is false, embeddings are gone
```

**Step 3: Refresh page to trigger auto-sync**
```
1. Refresh browser (F5)
2. Wait 2 seconds for DOMContentLoaded
3. Button should update
```

**Solutions:**

| Situation | Action |
|-----------|--------|
| **Embeddings exist but button disabled** | Refresh page to sync |
| **Embeddings gone but button shows ✅** | Refresh page to reset state |
| **Want to re-analyze** | Click button again (will override) |
| **Button still won't enable** | Clear browser cache (Ctrl+Shift+Del) |

---

### Issue 3: Analysis Fails, Button Stuck in Error State

**Symptoms:**
- Click "🔍 Analizar"
- Get error message
- Button shows "❌ Error" and is disabled
- Can't retry

**Expected Behavior (with fix):**
- Button should show "🔍 Reintentar"
- Button should be enabled
- User can click again

**Diagnosis:**

**Step 1: Check browser console for the error message**
```javascript
// The error alert shows what went wrong
// Common errors:
- "Error: No autenticado..."  → Login expired
- "Error: Módulo no encontrado"  → Wrong module ID
- "Error: Timeout"  → Canvas API too slow
- "Error: Network error"  → No internet
```

**Step 2: Check Django logs**
```bash
# Look in Django terminal output for:
ERROR - analyzing module 2: ...
```

**Step 3: Check if Canvas API is accessible**
```bash
# Verify Canvas connectivity
curl https://canvas.instructure.com/api/v1/courses \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Step 4: Try analyzing again**
```
1. Click button (should show "🔍 Reintentar")
2. Fix the underlying issue
3. Click again
```

**Solutions:**

| Error | Solution |
|-------|----------|
| **"No autenticado"** | Login again: click "Conectar con Canvas" |
| **"Módulo no encontrado"** | Module ID wrong or deleted, refresh to see current modules |
| **"Timeout"** | Canvas API slow, try again in 30s |
| **"Network error"** | Check internet, Canvas API status |
| **Other errors** | Check Django logs for details |

---

### Issue 4: Endpoint Returns 404

**Symptoms:**
```
GET /api/module/2/analysis-status/ → 404 Not Found
```

**Causes:**

**Cause 1: Django not restarted**
```bash
# Restart Django to load new routes
python manage.py runserver 127.0.0.1:8000
```

**Cause 2: Wrong URL format**
```javascript
// ❌ WRONG:
fetch('/api/module/analysis-status/2/')

// ✅ CORRECT:
fetch('/api/module/2/analysis-status/')
```

**Cause 3: Module ID is invalid**
```javascript
// Check that module ID exists
const moduleId = btn.dataset.moduleId;  // Should be a number
console.log('Module ID:', moduleId);   // Debug log
```

**Solutions:**

```bash
# 1. Restart Django
python manage.py runserver 127.0.0.1:8000
ps aux | grep runserver

# 2. Verify URL routing
python manage.py showurls
# Should show: /api/module/<int:module_id>/analysis-status/

# 3. Test with valid module ID
curl http://127.0.0.1:8000/api/module/2/analysis-status/
```

---

### Issue 5: Frontend Not Updating Button

**Symptoms:**
- Analysis completes
- Get success message
- But button doesn't update to "✅ Analizado"
- Button still shows "⏳ Analizando..."

**Diagnosis:**

**Step 1: Check browser console**
```javascript
// Look for JavaScript errors
// e.g.: "btn is undefined", "Cannot read property 'textContent'"
```

**Step 2: Check button element**
```javascript
// In console:
const btn = document.getElementById('analyzeBtn');
console.log(btn);  // Should show button element

// If null, button doesn't have correct ID
```

**Step 3: Verify button click handler**
```
1. Open DevTools (F12)
2. Right-click button
3. Select "Inspect Element"
4. Check if button has onclick="analyzeModule()"
```

**Solutions:**

| Problem | Fix |
|---------|-----|
| **Button ID wrong** | Make sure button ID matches script |
| **Element not found** | Refresh page, check HTML |
| **Click not firing** | Check Dev Tools → Events tab |
| **CSS not updating** | Hard refresh (Ctrl+Shift+R) |

---

### Issue 6: Embeddings Lost After Restart

**Symptoms:**
- Analyze module (button becomes ✅)
- Restart Django server
- Refresh page
- Button shows 🔍 (state lost)
- No embeddings available

**Root Cause:**
- Embeddings stored in RAM only (in-memory)
- RAM cleared on restart
- This is EXPECTED with current setup

**Solutions:**

**Option 1: Understand it's expected behavior** ✅
```
This is normal with in-memory storage
Read: EMBEDDING_PERSISTENCE_STRATEGY.md
Plan for long-term solution
```

**Option 2: Quick fix - Re-analyze after restart**
```
1. Restart Django
2. Open http://127.0.0.1:8000/
3. Click "🔍 Analizar" again
4. Wait for completion
5. Embeddings back (until next restart)
```

**Option 3: Implement persistence** (Recommended)
```
1. Implement Option A from EMBEDDING_PERSISTENCE_STRATEGY.md
2. Create StoredEmbedding model
3. Save embeddings to database
4. Load from database on startup
5. Survives restarts!
```

---

## Debug Commands

### Check Endpoint Status
```bash
# Test endpoint
curl http://127.0.0.1:8000/api/module/2/analysis-status/

# Pretty print JSON
curl http://127.0.0.1:8000/api/module/2/analysis-status/ | python -m json.tool
```

### Check Embeddings Status
```bash
# See all analyzed documents
curl http://127.0.0.1:8000/api/debug/documents/

# Filter by module
curl "http://127.0.0.1:8000/api/debug/documents/?module_id=2"
```

### Check Django Logs
```bash
# If running in Terminal:
# Look for "Starting RAG analysis"
# Look for "Module X analysis completed"
# Look for "Error analyzing module"
```

### Browser Console Commands
```javascript
// Test fetch directly
fetch('/api/module/2/analysis-status/')
    .then(r => r.json())
    .then(d => console.log('Status:', d));

// Force sync button
syncModuleAnalysisStatus(2, document.querySelector('[data-module-id="2"]'));

// Check all buttons
document.querySelectorAll('.analyze-btn').forEach(btn => {
    console.log('Button:', btn.dataset.moduleId, btn.textContent);
});
```

### Clear Browser Cache
```
Ctrl+Shift+Del → Select "Cookies and other site data"
→ "All time" → Clear data
```

---

## Performance Tips

### If Sync is Slow

**Problem:** Page takes 5+ seconds to load buttons

**Solution:**

**Option 1: Reduce checks**
```javascript
// Only sync visible buttons
document.querySelectorAll('.analyze-btn:visible').forEach(btn => {
    syncModuleAnalysisStatus(btn.dataset.moduleId, btn);
});
```

**Option 2: Parallel requests**
```javascript
// Current: Sequential (slow)
buttons.forEach(btn => syncModuleAnalysisStatus(...));

// Better: Parallel
Promise.all(buttons.map(btn => syncModuleAnalysisStatus(...)));
```

**Option 3: Cache results**
```javascript
// Add to localStorage
localStorage.setItem(`module_${id}_status`, JSON.stringify(data));

// Use cache if fresh
const cached = localStorage.getItem(`module_${id}_status`);
if (cached && isFresh(cached)) {
    // Use cached result
}
```

---

## Success Checklist

### ✅ Everything Working?

- [ ] Page loads without errors
- [ ] Buttons show correct state (✅ or 🔍)
- [ ] Can click "🔍 Analizar" and analysis starts
- [ ] Analysis completes and button becomes ✅
- [ ] Refresh page → button still ✅
- [ ] Error shows "🔍 Reintentar" not "❌ Error"
- [ ] Can retry after error
- [ ] Console has no red errors

### ✅ Ready for Next Phase?

If all above passed:
- [ ] Decide on persistence strategy (see EMBEDDING_PERSISTENCE_STRATEGY.md)
- [ ] Plan Option A implementation (recommended)
- [ ] Estimate timeline (1-2 hours)

---

## Getting Help

If still stuck:

1. **Check this guide first** → Section on your error
2. **Look at Django logs** → Terminal output
3. **Use browser DevTools** → F12 → Console/Network
4. **Test endpoint manually** → `curl` command
5. **Try hard refresh** → Ctrl+Shift+R
6. **Restart Django** → Ctrl+C, then `python manage.py runserver`

---

## Reference URLs

- **Dashboard:** http://127.0.0.1:8000/
- **Debug Events:** http://127.0.0.1:8000/api/debug/events/
- **Documents:** http://127.0.0.1:8000/api/debug/documents/
- **Module Status:** http://127.0.0.1:8000/api/module/2/analysis-status/
- **Django Admin:** http://127.0.0.1:8000/admin/

---

## Documentation Map

| Document | Purpose |
|----------|---------|
| `STATE_SYNCHRONIZATION_GUIDE.md` | How button sync works |
| `EMBEDDING_PERSISTENCE_STRATEGY.md` | Long-term solutions |
| `IMPLEMENTATION_SUMMARY.md` | What changed |
| `TROUBLESHOOTING_GUIDE.md` | This file |

---

**Last Updated:** 2026-02-15
**Status:** ✅ Complete & Working
