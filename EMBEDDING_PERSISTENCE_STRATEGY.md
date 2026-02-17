# Embedding Persistence Strategy - Long Term Solutions

## User Question
"¿Lo mejor es que cada vez los analice y los embeddings se borren cada vez que cierro, o que se guarden para la siguiente sesión de desarrollo?"

**Translation:** "Is it better to regenerate embeddings each time or save them for the next dev session?"

---

## Option Comparison

### Option A: Persist to SQLite ⭐ RECOMMENDED (Dev) ⭐

**How it works:**
- Create Django model to store embeddings in database
- After analysis, save embeddings to DB
- On server startup, load embeddings from DB
- Faster development cycle, no re-analysis needed

**Pros:**
- ✅ Embeddings survive server restarts
- ✅ No extra API calls after initial analysis
- ✅ Simple Django ORM integration
- ✅ Works with existing architecture
- ✅ Easy to migrate to PostgreSQL for production
- ✅ Can manage embeddings via Django admin

**Cons:**
- ❌ Database grows quickly (384 dims × N documents)
- ❌ Slightly slower than in-memory (disk I/O)
- ❌ Need migrations if schema changes

**Storage Estimate:**
```
Per embedding: 384 dimensions × 4 bytes (float32) ≈ 1.5 KB
Per module: 50 items × 1.5 KB ≈ 75 KB
Per course: 10 modules × 75 KB ≈ 750 KB
Per user: ~2-5 MB (reasonable)
```

**Implementation Example:**
```python
# models.py
class StoredEmbedding(models.Model):
    module = ForeignKey(Module, on_delete=CASCADE)
    item_id = CharField()
    item_title = CharField()
    embedding = BinaryField()  # Serialized 384-dim vector
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

# rag_service.py
def analyze_module(self, module, user_token):
    # ... existing analysis code ...
    
    # NEW: Save to database
    for doc, emb in zip(collection['documents'], collection['embeddings']):
        StoredEmbedding.objects.create(
            module=module,
            item_id=doc['item_id'],
            item_title=doc['title'],
            embedding=pickle.dumps(emb)  # Serialize vector
        )

def load_embeddings_from_db(self, collection_name):
    # Load on startup
    embeddings = StoredEmbedding.objects.filter(...)
    for emb_obj in embeddings:
        self.in_memory_db[collection_name]['embeddings'].append(
            pickle.loads(emb_obj.embedding)
        )
```

**Best For:** ✅ Development with persistent data between restarts

**Timeline:** 1-2 hours to implement

---

### Option B: Auto-Regenerate ⭐ SIMPLE

**How it works:**
- Keep current in-memory storage (no changes)
- On server startup, automatically re-analyze all modules
- Always have fresh, up-to-date embeddings
- No persistence code needed

**Pros:**
- ✅ Very simple (no DB changes)
- ✅ Always fresh data
- ✅ Works with current architecture
- ✅ Minimal code changes

**Cons:**
- ❌ Slow startup if many modules (Canvas API calls)
- ❌ Uses Canvas API quota every restart
- ❌ Annoying delays during development
- ❌ Data lost if Canvas API fails during startup

**Startup Performance:**
```
1 module with 50 items: ~30-60 seconds
5 modules: ~2-5 minutes
10 modules: ~5-10 minutes
(Canvas API is slow)
```

**Implementation:**
```python
# Startup hook - called when Django starts
def startup_analysis():
    for module in Module.objects.all():
        rag_service.analyze_module(module, user_token)
        print(f"Auto-analyzed {module.name}")

# In manage.py or settings
if os.environ.get('AUTO_ANALYZE'):
    startup_analysis()
```

**Best For:** ✅ Small projects, quick testing, always-fresh data

**Timeline:** 30 minutes to implement

---

### Option C: Hybrid (Best Practice) ⭐⭐ PRODUCTION READY ⭐⭐

**How it works:**
- Persist embeddings to database (like Option A)
- On startup, load from DB (fast)
- Periodically re-analyze (keep fresh)
- Manual force-refresh available

**Pros:**
- ✅ Fast startup (loads from DB)
- ✅ Always up-to-date (periodic refresh)
- ✅ User control (force-refresh button)
- ✅ Production-ready architecture
- ✅ Easy to add new items to modules
- ✅ Can schedule analysis at off-peak times

**Cons:**
- ❌ More complex implementation
- ❌ Need background job scheduler (Celery)
- ❌ Database storage costs

**Architecture:**
```
Startup:
├─ Load embeddings from DB (fast)
└─ Periodic task (every N hours/days)
   └─ Re-analyze all modules
      └─ Update embeddings in DB

Manual:
└─ Admin panel: "Force re-analyze" button
   └─ Immediately refresh embeddings
```

**Implementation Sketch:**
```python
# Startup
def startup():
    for module in Module.objects.all():
        StoredEmbedding.load_for_module(module)  # Instant

# Background job (using Celery)
@periodic_task(run_every=crontab(hour=2, minute=0))
def refresh_embeddings():
    for module in Module.objects.all():
        rag_service.analyze_module(module)
        StoredEmbedding.objects.filter(module=module).delete()
        StoredEmbedding.objects.create(...)

# Manual
def force_refresh_view(request, module_id):
    module = Module.objects.get(id=module_id)
    rag_service.analyze_module(module)
    return JsonResponse({'status': 'refreshed'})
```

**Best For:** ✅ Production systems, long-term projects, guaranteed data freshness

**Timeline:** 3-4 hours to implement with Celery

---

## Decision Matrix

| Aspect | Option A (Persist) | Option B (Regenerate) | Option C (Hybrid) |
|--------|---|---|---|
| **Startup Time** | <1s ⚡ | 2-10 min 🐌 | <1s ⚡ |
| **Freshness** | On-demand 📅 | Always fresh 🆕 | Always fresh 🆕 |
| **Complexity** | Medium 🟡 | Low 🟢 | High 🔴 |
| **API Quota** | Minimal | High | Medium |
| **Dev Experience** | Good ✅ | Slow ❌ | Best ✅✅ |
| **Production Ready** | Yes ✅ | No ❌ | Yes ✅✅ |
| **DB Storage** | ~5MB/user | None | ~5MB/user |
| **Recommended For** | Dev & Prod | Testing Only | Production |

---

## My Recommendation

**For You (Right Now):**

### **Start with Option A (Persist to SQLite)** ✅

**Why:**
1. You're still in development - need data persistence
2. Server restarts happen frequently
3. Simple to implement (1-2 hours)
4. Easy to migrate to Option C later
5. No external dependencies (just Django + SQLite)
6. Works immediately after analysis

**Next Phase (When Ready):**
1. If startup slows down → Move to Option C
2. If want production-ready → Add Celery background tasks
3. Can always switch to PostgreSQL later

---

## Implementation Guide for Option A

### Step 1: Create Model
```python
# tu_app/models.py
import pickle
import numpy as np

class StoredEmbedding(models.Model):
    """Store embeddings in database for persistence"""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='embeddings')
    item_id = models.CharField(max_length=255)  # Canvas item ID
    item_title = models.CharField(max_length=500)
    item_type = models.CharField(max_length=50)  # "Page", "Discussion", etc.
    content_preview = models.TextField(max_length=500)
    embedding = models.BinaryField()  # Pickled numpy array
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['module', 'item_id']),
        ]
    
    def get_embedding(self):
        """Convert binary to numpy array"""
        return pickle.loads(self.embedding)
    
    @staticmethod
    def save_embedding(module, item_id, title, item_type, content, embedding_vector):
        """Save embedding to database"""
        StoredEmbedding.objects.update_or_create(
            module=module,
            item_id=item_id,
            defaults={
                'item_title': title,
                'item_type': item_type,
                'content_preview': content[:500],
                'embedding': pickle.dumps(embedding_vector)
            }
        )
```

### Step 2: Modify RAG Service
```python
# tu_app/rag_service.py

def analyze_module(self, module, user_token: str) -> bool:
    # ... existing analysis code ...
    
    # After creating embeddings:
    for i, item_id in enumerate(item_ids):
        try:
            # Save to database
            if hasattr(self, '_save_to_db'):
                self._save_to_db(
                    module=module,
                    item_id=item_id,
                    title=item_titles[i],
                    embedding=embeddings[i]
                )
        except Exception as e:
            logger.warning(f"Failed to save embedding to DB: {e}")

def load_embeddings_from_db(self, module):
    """Load embeddings from database on startup"""
    try:
        from tu_app.models import StoredEmbedding
        
        collection_name = f"module_{module.id}_course_{module.course.id}"
        embeddings_qs = StoredEmbedding.objects.filter(module=module)
        
        if not embeddings_qs.exists():
            return False  # Not in DB yet
        
        collection = {
            'documents': [],
            'embeddings': [],
            'metadatas': []
        }
        
        for emb_obj in embeddings_qs:
            collection['documents'].append({
                'item_id': emb_obj.item_id,
                'title': emb_obj.item_title,
                'type': emb_obj.item_type
            })
            collection['embeddings'].append(emb_obj.get_embedding())
            collection['metadatas'].append({
                'item_id': emb_obj.item_id,
                'title': emb_obj.item_title
            })
        
        self.in_memory_db[collection_name] = collection
        logger.info(f"Loaded {len(embeddings_qs)} embeddings from DB for {collection_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error loading from DB: {e}")
        return False
```

### Step 3: Create Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 4: Load on Startup
```python
# tu_app/apps.py
from django.apps import AppConfig

class TuAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tu_app'
    
    def ready(self):
        """Load embeddings from DB when Django starts"""
        from tu_app.models import Module
        from tu_app.rag_service import get_rag_service
        
        rag_service = get_rag_service()
        try:
            for module in Module.objects.all():
                loaded = rag_service.load_embeddings_from_db(module)
                if loaded:
                    logger.info(f"Loaded embeddings for {module.name}")
        except Exception as e:
            logger.warning(f"Could not load embeddings on startup: {e}")
```

---

## Testing Your Choice

### For Option A (Persist):
```
1. Analyze a module
2. Check DB: SELECT COUNT(*) FROM tu_app_storededbedding WHERE module_id=1;
3. Restart Django
4. Embeddings still in memory?
5. Delete embeddings manually from DB
6. Query again - should be gone
```

### For Option B (Regenerate):
```
1. Start Django with AUTO_ANALYZE=true
2. Wait for auto-analysis
3. Check that all modules analyzed
4. Restart Django
5. Should see analysis running again
```

### For Option C (Hybrid):
```
1. Analyze module (saves to DB)
2. Restart Django (loads from DB - fast!)
3. Run periodic task manually
4. Embeddings re-created
5. Check that fresh data is used
```

---

## Cost Comparison

| Option | Dev Startup | API Calls | Storage | Complexity |
|--------|---|---|---|---|
| **A** | <1s ⚡ | 1x (initial) | ~5MB | 2h |
| **B** | 2-10m 🐌 | ∞ (every restart) | 0 | 30m |
| **C** | <1s ⚡ | 1x + periodic | ~5MB | 3-4h |

---

## My Final Recommendation

**Choose Option A (Persist) RIGHT NOW because:**

1. ✅ **You're in development** - restarts are frequent
2. ✅ **Need fast feedback loop** - waiting 5 minutes each restart kills productivity  
3. ✅ **Easy migration path** - can upgrade to Option C later
4. ✅ **Simple implementation** - just add one model (1-2 hours)
5. ✅ **Works immediately** - no external dependencies

**If later you need Option C:**
- Keep Option A code
- Add Celery tasks on top
- No need to rewrite

---

## Next Steps

Want me to implement Option A for you?

**I can:**
1. Create `StoredEmbedding` model
2. Update `RAGService` to save/load
3. Create migrations
4. Add startup hook
5. Test the full cycle

**You'll need to:**
1. Run migrations: `python manage.py migrate`
2. Optionally force re-analysis first time

**Result:** Embeddings persist across restarts! 🎉

---

## Questions?

- Need production setup? → Go with Option C
- Want minimal changes? → Stay with Option B (for now)
- Want best of both? → Go with Option A (recommended)
- Need cost analysis for cloud? → Can provide PostgreSQL+ S3 strategy
