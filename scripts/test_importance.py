import os
import sys
import json

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Initialise Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
import django
django.setup()

from tu_app.rag_service import RAGService

rs = RAGService(persistent_dir=os.path.join(PROJECT_ROOT, 'tmp_chroma'))
chunks = [
    "Definición: Se define como un proceso que transforma datos en información relevante.",
    "Ejemplo: Por ejemplo, en la figura se muestra un caso que ilustra el punto.",
    "Conclusión: En resumen, lo importante es identificar patrones y resultados.",
    "Detalle técnico: La fórmula es X = Y + Z y se aplica en condiciones específicas.",
]
scores = rs._calculate_importance_batch(chunks, document_title='Documento de prueba')
out = [{'chunk': c, 'score': round(s, 3)} for c, s in zip(chunks, scores)]
print(json.dumps(out, ensure_ascii=False, indent=2))
