import django, os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "kairos_project.settings"
sys.path.insert(0, "/opt/kairos")
django.setup()
from tu_app.vector_store import get_vector_store
vs = get_vector_store(persist_dir="/opt/kairos/.chroma_db", json_dir="/opt/kairos/.embeddings")
col = vs.client.get_collection("module_2_course_1")
total = col.count()
print("Total docs:", total)
sample = col.get(limit=15, include=["documents","metadatas"])
for i in range(len(sample["documents"])):
    doc = sample["documents"][i]
    meta = sample["metadatas"][i]
    title = meta.get("item_title", "?")[:50]
    imp = meta.get("importance_score", "?")
    print("--- Doc %d (len=%d, imp=%s) item=%s ---" % (i, len(doc), imp, title))
    print(doc[:200])
    print()

# Size distribution
sizes = [len(d) for d in col.get(include=["documents"])["documents"]]
sizes.sort()
print("=== SIZE DISTRIBUTION ===")
print("Min:", min(sizes))
print("Max:", max(sizes))
print("Avg:", sum(sizes)//len(sizes))
print("Median:", sizes[len(sizes)//2])
under50 = sum(1 for s in sizes if s < 50)
under100 = sum(1 for s in sizes if s < 100)
print("Under 50 chars:", under50)
print("Under 100 chars:", under100)
print("Total:", len(sizes))
