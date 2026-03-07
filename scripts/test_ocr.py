#!/usr/bin/env python3
"""
Quick OCR diagnostic — run on the droplet to verify Surya is working.

Usage:
    source /opt/kairos/venv/bin/activate
    python scripts/test_ocr.py

It creates a tiny test image with text + math symbols and runs the
full OCR pipeline (LayoutPredictor → Recognition / Texify).
"""

import sys
import os

# Add project root so Django imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")

def main():
    print("=" * 60)
    print("Kairos OCR diagnostic")
    print("=" * 60)

    # 1. Check imports
    print("\n[1] Checking imports...")
    try:
        from PIL import Image, ImageDraw, ImageFont
        print("    ✓ Pillow OK")
    except ImportError as e:
        print(f"    ✗ Pillow FAILED: {e}")
        return

    try:
        import surya
        print(f"    ✓ surya-ocr OK (version: {getattr(surya, '__version__', '?')})")
    except ImportError as e:
        print(f"    ✗ surya-ocr FAILED: {e}")
        return

    try:
        from surya.recognition import RecognitionPredictor
        print("    ✓ RecognitionPredictor importable")
    except ImportError as e:
        print(f"    ✗ RecognitionPredictor import FAILED: {e}")

    try:
        from surya.detection import DetectionPredictor
        print("    ✓ DetectionPredictor importable")
    except ImportError as e:
        print(f"    ✗ DetectionPredictor import FAILED: {e}")

    try:
        from surya.foundation import FoundationPredictor
        print("    ✓ FoundationPredictor importable")
    except ImportError as e:
        print(f"    ✗ FoundationPredictor import FAILED: {e}")

    try:
        from surya.common.surya.schema import TaskNames
        print(f"    ✓ TaskNames importable (LaTeX task = {TaskNames.block_without_boxes})")
    except ImportError as e:
        print(f"    ✗ TaskNames import FAILED: {e}")

    try:
        import transformers
        print(f"    ✓ transformers version: {transformers.__version__}")
    except ImportError as e:
        print(f"    ✗ transformers FAILED: {e}")

    # 2. Create a test image with text and a "formula-like" region
    print("\n[2] Creating test image...")
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 20), "Hello, this is a test.", fill="black", font=font)
    draw.text((20, 70), "∫ f(x) dx = F(x) + C", fill="black", font=font)
    draw.text((20, 120), "x² + y² = r²", fill="black", font=font)

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()
    print(f"    ✓ Test image created ({len(image_bytes)} bytes)")

    # 3. Run OCR service
    print("\n[3] Running OCR service (this may download models on first run)...")
    try:
        # Set up Django minimally
        import django
        django.setup()
        from tu_app.ocr_service import get_ocr_service
        ocr = get_ocr_service()
        result = ocr.extract_text(image_bytes)
        print(f"\n{'=' * 60}")
        print("OCR RESULT:")
        print(f"{'=' * 60}")
        print(result if result else "(empty — no text extracted)")
        print(f"{'=' * 60}")
        if result:
            print(f"\n    ✓ SUCCESS — {len(result)} chars extracted")
            if "$" in result:
                print("    ✓ LaTeX detected in output")
            else:
                print("    ⚠ No LaTeX delimiters found (Texify may not have triggered)")
        else:
            print("\n    ✗ FAILED — OCR returned empty string")
    except Exception as e:
        print(f"\n    ✗ OCR FAILED with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
