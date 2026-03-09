import os
import sys
import json

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
import django
django.setup()

from tu_app.query_analyzer import get_query_analyzer
from tu_app.rag_service import RAGService

QUESTION = 'un resumen de todo'
MODULE_ID = 1
COURSE_ID = 1

qa = get_query_analyzer()
analysis = qa.analyze(QUESTION)
print('=== Query analysis ===')
print(json.dumps(analysis, ensure_ascii=False, indent=2))

rs = RAGService()
num_fragments = analysis.get('num_fragments', 5)
importance_weight = analysis.get('importance_weight')
search_terms = analysis.get('search_terms')

results = rs.search_context(
    query=QUESTION,
    module_id=MODULE_ID,
    course_id=COURSE_ID,
    top_k=num_fragments,
    query_type=analysis.get('query_type', 'general'),
    importance_weight=importance_weight,
    search_terms=search_terms,
)

print('\n=== Top results ===')
for i, r in enumerate(results, start=1):
    meta = r.get('metadata', {})
    print(f"{i}. combined={r.get('combined_score'):.3f} | relevance={r.get('relevance_score'):.3f} | importance={r.get('importance_score'):.3f} | kw_boost={r.get('keyword_boost'):.3f}")
    print('   meta importance_score:', meta.get('importance_score'))
    print('   excerpt:', (r.get('content') or '')[:200].replace('\n',' '))
    print()

print('Total returned:', len(results))
