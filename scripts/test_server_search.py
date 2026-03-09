import os, sys, json
sys.path.insert(0, '/opt/kairos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
import django; django.setup()

from tu_app.query_analyzer import get_query_analyzer
from tu_app.rag_service import RAGService

QUESTION = 'un resumen de todo'
MODULE_ID = 1
COURSE_ID = 1

qa = get_query_analyzer()
analysis = qa.analyze(QUESTION)
print('=== Query analysis ===')
print(json.dumps({k:v for k,v in analysis.items() if k != '_debug'}, ensure_ascii=False, indent=2))
print('search_terms:', analysis['search_terms'])

rs = RAGService()
results = rs.search_context(
    query=QUESTION,
    module_id=MODULE_ID,
    course_id=COURSE_ID,
    top_k=analysis.get('num_fragments', 5),
    query_type=analysis.get('query_type', 'general'),
    importance_weight=analysis.get('importance_weight'),
    search_terms=analysis.get('search_terms'),
)

print(f'\n=== Top {len(results)} results ===')
for i, r in enumerate(results, start=1):
    meta = r.get('metadata', {})
    print(f"{i}. combined={r['combined_score']:.3f} | rel={r['relevance_score']:.3f} | imp={r['importance_score']:.3f} | kw={r['keyword_boost']:.3f} | meta_imp={meta.get('importance_score','?')}")
    print(f"   title: {meta.get('item_title','?')[:60]}")
    print(f"   excerpt: {(r.get('content',''))[:150].replace(chr(10),' ')}")
    print()
