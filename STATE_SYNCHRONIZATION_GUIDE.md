# State Synchronization & Error Recovery Guide

## Problem Statement

**Original Issues:**
1. ❌ "Analyze" button shows "Analyzed" status after page reload, but embeddings are lost
2. ❌ Error states on buttons don't clear - they stick
3. ❌ Embeddings lost when Django server restarts (in-memory storage)
4. ❌ Frontend button state ≠ Backend data state

**Root Causes:**
- Backend stores embeddings in Python dictionary (`in_memory_db`) - lost on restart
- Frontend stores button state in DOM/classes - persists across page reloads
- No synchronization mechanism between frontend and backend on page load
- No error recovery mechanism

---

## Solution Implemented

### 1. New Backend Endpoint: `/api/module/<module_id>/analysis-status/`

**Purpose:** Check if a module has embeddings and return the REAL state

**Response:**
```json
{
    "status": "ok",
    "module_id": 2,
    "is_analyzed": true,
    "document_count": 5,
    "db_status": "completed",
    "has_embeddings": true,
    "collection_name": "module_2_course_1"
}
```

**Implementation Details:**
- Checks `debug_service.get_analyzed_documents()` - returns docs registered during analysis
- Checks `rag_service.check_collection_exists()` - verifies embeddings are stored
- Returns truth from both sources - most reliable
- Falls back gracefully if check fails

**File:** [tu_app/views.py](tu_app/views.py#L522-L575)
```python
def check_module_analysis_status(request, module_id):
    """Verify if module has embeddings (state sync endpoint)"""
```

---

### 2. New RAGService Method: `check_collection_exists()`

**Purpose:** Check if a collection exists and has embeddings

**Logic:**
```python
def check_collection_exists(self, collection_name: str) -> bool:
    # 1. Check in ChromaDB if available
    if self.using_chromadb and self.client:
        collection = self.client.get_collection(collection_name)
        return collection.count() > 0
    
    # 2. Check in-memory `in_memory_db`
    if collection_name in self.in_memory_db:
        docs = self.in_memory_db[collection_name]['documents']
        return len(docs) > 0
    
    # 3. Neither found - return False
    return False
```

**File:** [tu_app/rag_service.py](tu_app/rag_service.py#L354-L382)

---

### 3. Frontend State Synchronization

**Key Changes:**

#### On Page Load (DOMContentLoaded)
```javascript
document.addEventListener('DOMContentLoaded', function() {
    const analyzeButtons = document.querySelectorAll('.analyze-btn');
    
    analyzeButtons.forEach(btn => {
        const moduleId = btn.dataset.moduleId;
        syncModuleAnalysisStatus(moduleId, btn);  // ← Check real state
    });
});
```

**What This Does:**
- Queries backend for each module's real status
- Updates button text and color based on actual data
- Prevents stale UI state after page reload

#### The Sync Function
```javascript
function syncModuleAnalysisStatus(moduleId, button) {
    fetch(`/api/module/${moduleId}/analysis-status/`)
        .then(response => response.json())
        .then(data => {
            if (data.is_analyzed && data.document_count > 0) {
                // Real data exists
                button.textContent = '✅ Analizado';
                button.style.background = '#28a745';
                button.disabled = true;
            } else {
                // No real data
                button.textContent = '🔍 Analizar';
                button.style.background = '#6c757d';
                button.disabled = false;
            }
        });
}
```

**Result:**
- ✅ Accurate button state on every page load
- ✅ Reflects actual backend data
- ✅ No stale UI

**Files Updated:**
- [tu_app/templates/tu_app/index.html](tu_app/templates/tu_app/index.html#L189-L245) - Dashboard
- [tu_app/templates/tu_app/module_detail.html](tu_app/templates/tu_app/module_detail.html#L127-L196) - Module detail view

---

### 4. Error Recovery Mechanism

**Before (Broken):**
```javascript
button.textContent = '❌ Error';  // Stuck forever
```

**After (Fixed):**
```javascript
// On error, set button back to "retry" state
if (data.error || error.message) {
    button.textContent = '🔍 Reintentar';  // ← Allows retry
    button.disabled = false;  // ← Can click again
    button.style.background = '#6c757d';
}
```

**What Changed:**
1. Errors show "Reintentar" (Retry) instead of "Error"
2. Button doesn't stay disabled after error
3. User can click again immediately
4. State re-synced with backend after error

**Result:**
- ✅ Errors are recoverable
- ✅ Can retry failed analysis
- ✅ No need to refresh page to recover

---

## How the System Now Works

### Flow 1: User Opens Dashboard
```
1. Browser loads index.html
   ↓
2. DOMContentLoaded event fires
   ↓
3. JavaScript calls syncModuleAnalysisStatus() for each module
   ↓
4. Frontend queries /api/module/<id>/analysis-status/
   ↓
5. Backend checks:
   - debug_service.get_analyzed_documents() ?
   - rag_service.check_collection_exists() ?
   ↓
6. Backend returns real state {is_analyzed: true/false}
   ↓
7. Frontend updates button color & text to match reality
   ↓
8. User sees ACCURATE button state
   ✅ RESULT: No stale buttons!
```

### Flow 2: User Clicks "Analyze"
```
1. Button click event
   ↓
2. Button set to "⏳ Analizando..." (yellow)
   ↓
3. POST /api/analyze-module/<id>/
   ↓
4. Backend analyzes and creates embeddings
   ↓
5. Response: {status: 'completed'}
   ↓
6. Button set to "✅ Analizado" (green)
   ↓
   ✅ RESULT: Analysis complete, embeddings saved
```

### Flow 3: Analysis Fails
```
1. POST /api/analyze-module/<id>/ returns error
   ↓
2. Button set to "🔍 Reintentar" (gray)
   ↓
3. Button NOT disabled (user can click again)
   ↓
4. User clicks again to retry
   ↓
   ✅ RESULT: User can recover without page refresh
```

### Flow 4: Server Restart (Current)
```
1. Django server restarts
   ↓
2. in_memory_db is cleared (expected behavior)
   ↓
3. User refreshes browser
   ↓
4. DOMContentLoaded event fires
   ↓
5. syncModuleAnalysisStatus() called for each module
   ↓
6. Backend returns {is_analyzed: false, document_count: 0}
   ↓
7. Frontend updates button to "🔍 Analizar"
   ↓
   ✅ RESULT: Button now shows correct state!
   (Embeddings are gone, but button reflects this)
```

---

## What's Still Missing (Next Steps)

### Issue: Embeddings Lost on Server Restart

**Current Behavior:**
- Embeddings stored in `in_memory_db` (Python dict)
- On Django restart, all data lost
- User loses analysis work with every server restart
- Need to re-analyze after every dev restart

**Options for Next Phase:**

### Option A: Persist to SQLite (Recommended)
**Pros:**
- ✅ Simple with Django ORM
- ✅ Works for dev and prod
- ✅ Easy to query
- ✅ Automatic migration support

**Cons:**
- Embeddings are large (384 dimensions per doc)
- Need custom storage model

**Implementation:**
```python
# New model
class StoredEmbedding(models.Model):
    module = ForeignKey(Module)
    item_id = CharField()
    embedding = BinaryField()  # 384-dim vector
    content = TextField()
    metadata = JSONField()

# Load on startup
rag_service.load_from_db()
```

### Option B: Auto-Regenerate (Simpler)
**Pros:**
- ✅ No persistence layer needed
- ✅ Always fresh data

**Cons:**
- Slow startup if many modules
- Uses Canvas API each restart

**Implementation:**
```python
# On startup, re-analyze all modules
def startup():
    for module in Module.objects.all():
        rag_service.analyze_module(module)
```

### Option C: Hybrid (Best)
**Pros:**
- ✅ Fast startup (load from DB)
- ✅ Always fresh (periodic sync)
- ✅ Survives restarts

**Implementation:**
```python
# Startup
for module in Module.objects.all():
    if not module.has_fresh_embeddings():
        regenerate()
    else:
        load_from_db()

# Periodic sync (every N minutes)
schedule_periodic_analysis()
```

---

## Current Architecture

```
Frontend                        Backend
─────────                       ────────

index.html/                  
module_detail.html          
     │                            
     ├─→ DOMContentLoaded ─────→ check_module_analysis_status()
     │       (on page load)              │
     │                                    ├─→ debug_service.get_analyzed_documents()
     │                                    ├─→ rag_service.check_collection_exists()
     │                                    └─→ returns {is_analyzed, document_count}
     │
     ├─ Updates button state ← Returns JSON status
     │       (✅ or 🔍)
     │
     ├─→ Click "Analizar" ─────→ analyze_module_api()
     │                            │
     │                            ├─→ rag_service.analyze_module()
     │                            │       ├─→ Get Canvas items
     │                            │       ├─→ Generate embeddings
     │                            │       └─→ Store in-memory or ChromaDB
     │                            │
     │                            └─→ returns {status: 'completed'}
     │
     └─ Updates button to ✅
       (repeats if error)
```

---

## Testing the Solution

### Test 1: Button State Sync
```
1. Open http://127.0.0.1:8000/
2. Verify buttons show "🔍 Analizar" (not analyzed yet)
3. Refresh page
4. Buttons should STILL show "🔍 Analizar" ✅
   (State persists from page load verification)
```

### Test 2: After Analysis
```
1. Click "🔍 Analizar" button
2. Wait for completion
3. Button changes to "✅ Analizado"
4. Refresh page
5. Button STILL shows "✅ Analizado" ✅
   (State reflects actual embeddings)
```

### Test 3: Stale State Recovery
```
1. Analyze a module (button becomes ✅)
2. Manually delete embeddings (backend reset)
3. Refresh page
4. Button shows "🔍 Analizar" (not ✅) ✅
   (State corrected by verification)
```

### Test 4: Error Recovery
```
1. Simulate error during analysis (break Canvas API call)
2. Click "🔍 Analizar"
3. Get error message
4. Button shows "🔍 Reintentar" (not disabled) ✅
5. Fix the issue
6. Click again - analysis retries ✅
```

---

## Key Files Modified

| File | Change | Purpose |
|------|--------|---------|
| [tu_app/views.py](tu_app/views.py#L522-L575) | Added `check_module_analysis_status()` | State verification endpoint |
| [tu_app/urls.py](tu_app/urls.py#L20) | Added route `/api/module/<id>/analysis-status/` | State endpoint route |
| [tu_app/rag_service.py](tu_app/rag_service.py#L354-L382) | Added `check_collection_exists()` | Check if embeddings exist |
| [tu_app/templates/tu_app/index.html](tu_app/templates/tu_app/index.html#L189-L245) | Added `syncModuleAnalysisStatus()` | Frontend state sync (dashboard) |
| [tu_app/templates/tu_app/module_detail.html](tu_app/templates/tu_app/module_detail.html#L127-L196) | Added `syncAnalysisStatus()` | Frontend state sync (detail view) |

---

## Troubleshooting

### Button still shows wrong state after refresh?
1. Open browser DevTools (F12)
2. Check Console for errors in `syncModuleAnalysisStatus()`
3. Go to Network tab
4. Check if `/api/module/<id>/analysis-status/` returns correct data
5. Verify backend has embeddings: `curl http://localhost:8000/api/debug/documents/`

### Endpoint returns 404?
1. Check that Django server is running with new code
2. Verify URL: `/api/module/2/analysis-status/` (module ID should be a number)
3. Restart Django: `python manage.py runserver`

### Still losing embeddings on restart?
That's expected with current in-memory storage. To fix:
- ✅ Next phase: Implement Option A (SQLite persistence)
- Or use Option C (Hybrid) for immediate improvement

---

## Summary

**Problems Fixed:**
- ✅ Stale button states after page reload
- ✅ Errors that stick forever (now recoverable)
- ✅ No sync between frontend and backend

**How It Works:**
1. On page load, verify state with backend
2. On error, enable retry mechanism
3. On data loss, button reflects reality

**Architecture:**
- Minimal changes (one new endpoint)
- Follows existing patterns
- No database schema changes needed

**Next Steps:**
1. Implement embedding persistence (SQLite)
2. Add auto-load from DB on startup
3. (Optional) Add periodic re-analysis
