import base64
import io
import json
import statistics
import time

import django
from PIL import Image, ImageDraw


def make_test_image_data_url() -> str:
    img = Image.new("RGB", (1200, 900), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 60), "Kairos OCR test image: integral x^2 dx", fill=(0, 0, 0))
    draw.text((50, 120), "Pregunta: explica este concepto en pasos", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def run_case(rf, user, payload, runs=3):
    wall_times = []
    step_timings = []
    errors = 0

    for _ in range(runs):
        t0 = time.perf_counter()
        req = rf.post(
            "/api/chat/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        req.user = user
        from tu_app.views import chat_api
        resp = chat_api(req)
        wall = time.perf_counter() - t0
        wall_times.append(wall)

        try:
            body = json.loads(resp.content.decode("utf-8"))
        except Exception:
            body = {"error": f"non-json response status={resp.status_code}"}

        if resp.status_code != 200 or not body.get("success"):
            errors += 1
            step_timings.append({"status": resp.status_code, "error": body.get("error", "unknown")})
            continue

        step_timings.append(body.get("timings", {}))

    return {
        "runs": runs,
        "errors": errors,
        "wall_avg_s": round(statistics.mean(wall_times), 3),
        "wall_min_s": round(min(wall_times), 3),
        "wall_max_s": round(max(wall_times), 3),
        "step_timings": step_timings,
    }


def summarize_steps(step_timings):
    valid = [t for t in step_timings if isinstance(t, dict) and "total_s" in t]
    if not valid:
        return {}

    keys = ["parse_s", "ocr_s", "preprocess_s", "analysis_s", "search_s", "ai_s", "db_s", "total_s"]
    summary = {}
    for k in keys:
        vals = [float(t.get(k, 0.0)) for t in valid]
        summary[k] = {
            "avg": round(statistics.mean(vals), 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
        }
    return summary


def main():
    django.setup()

    from django.contrib.auth.models import User
    from django.test import RequestFactory
    from tu_app.models import Course, Module
    from tu_app.ai_service_config import ACTIVE_PROVIDER
    from tu_app.ai_service import get_ai_service

    user = User.objects.first()
    course = Course.objects.filter(user=user).first()
    module = Module.objects.filter(course=course).first() if course else None

    if not user or not course:
        print(json.dumps({"error": "No user/course found for benchmark"}, ensure_ascii=False, indent=2))
        return

    rf = RequestFactory()

    model = get_ai_service().model

    payload_text = {
        "question": "Explica el teorema de Pitagoras con ejemplo rapido.",
        "course_id": course.id,
        "module_id": module.id if module else None,
    }

    payload_image = {
        "question": "Resume lo importante de la imagen.",
        "course_id": course.id,
        "module_id": module.id if module else None,
        "image_base64": make_test_image_data_url(),
    }

    text_result = run_case(rf, user, payload_text, runs=3)
    image_result = run_case(rf, user, payload_image, runs=3)

    output = {
        "provider": ACTIVE_PROVIDER,
        "model": model,
        "text_case": {
            **text_result,
            "step_summary": summarize_steps(text_result["step_timings"]),
        },
        "image_case": {
            **image_result,
            "step_summary": summarize_steps(image_result["step_timings"]),
        },
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
