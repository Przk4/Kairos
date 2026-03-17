import io
import os
import sys
import time
from PIL import Image, ImageDraw

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")

import django

django.setup()

from tu_app.models import Course, Module
from tu_app.ocr_service import get_ocr_service
from tu_app.rag_service import get_rag_service
from tu_app.query_analyzer import get_query_analyzer
from tu_app.question_preprocessor import get_question_preprocessor
from tu_app.ai_service import get_ai_service


def make_test_image_bytes(width=3000, height=2000):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Integral test: int x^2 dx, theorem and examples", fill=(0, 0, 0))
    draw.text((50, 120), "Pregunta: explica el concepto y resuelve un ejemplo", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def timed(fn):
    start = time.perf_counter()
    value = fn()
    elapsed = time.perf_counter() - start
    return value, elapsed


def main():
    question = "Explica integral de x^2 con un ejemplo sencillo"
    results = {}

    image_bytes = make_test_image_bytes()

    question_preprocessor = get_question_preprocessor()
    question_info, t_preprocess = timed(lambda: question_preprocessor.preprocess(question))
    interpreted_question = question_info.get("interpreted_question") or question
    results["preprocess_s"] = round(t_preprocess, 3)

    try:
        ocr, t_ocr = timed(lambda: get_ocr_service().extract_text(image_bytes))
        results["ocr_s"] = round(t_ocr, 3)
        results["ocr_chars"] = len(ocr or "")
        results["ocr_status"] = "ok"
    except Exception as exc:
        results["ocr_s"] = 0.0
        results["ocr_chars"] = 0
        results["ocr_status"] = f"unavailable: {exc}"

    rag_service = get_rag_service()
    analyzer = get_query_analyzer(rag_service.embedding_model)

    query_analysis, t_analysis = timed(lambda: analyzer.analyze(interpreted_question))
    results["analysis_s"] = round(t_analysis, 3)
    results["query_type"] = query_analysis.get("query_type")
    results["num_fragments"] = query_analysis.get("num_fragments")

    course = Course.objects.first()
    module = Module.objects.filter(course=course).first() if course else None

    if module and course:
        context, t_search = timed(
            lambda: rag_service.search_context(
                interpreted_question,
                module.id,
                course.id,
                top_k=query_analysis.get("num_fragments", 6),
                query_type=query_analysis.get("query_type", "general"),
                search_terms=query_analysis.get("search_terms"),
                importance_weight=query_analysis.get("importance_weight"),
            )
        )
    else:
        context, t_search = [], 0.0

    results["search_s"] = round(t_search, 3)
    results["context_count"] = len(context)

    ai_service = get_ai_service()
    ai_response, t_ai = timed(
        lambda: ai_service.answer_question(
            question=interpreted_question,
            context=context,
            user=None,
            question_metadata={
                **question_info,
                "analysis_question": interpreted_question,
            },
        )
    )
    results["ai_s"] = round(t_ai, 3)
    results["model"] = ai_response.get("model")
    results["tokens_used"] = ai_response.get("tokens_used", 0)

    total_s = results["preprocess_s"] + results["ocr_s"] + results["analysis_s"] + results["search_s"] + results["ai_s"]
    results["total_pipeline_s"] = round(total_s, 3)

    print("=== BENCHMARK CHAT PIPELINE ===")
    for key in [
        "model",
        "preprocess_s",
        "ocr_s",
        "ocr_chars",
        "analysis_s",
        "query_type",
        "num_fragments",
        "search_s",
        "context_count",
        "ai_s",
        "tokens_used",
        "total_pipeline_s",
    ]:
        print(f"{key}: {results.get(key)}")


if __name__ == "__main__":
    main()
