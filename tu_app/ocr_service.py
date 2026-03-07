"""
Kairos OCR Service — Image-to-text extraction with math formula support.

Engine:  Surya OCR  (local, no external API calls)
  - RecognitionPredictor  → text OCR (with DetectionPredictor for bbox detection)
  - RecognitionPredictor  → LaTeX for math (TaskNames.block_without_boxes)

Pipeline (memory-efficient — no LayoutPredictor):
  1. RecognitionPredictor extracts text from the full image.
  2. If the output looks garbled (many non-alphanumeric chars), the image
     is re-processed with the LaTeX task to produce math notation.
  3. Both results are assembled.

Used by:
  - Chat image uploads          (views.py  → extract_text / extract_text_from_base64)
  - Extension screenshot capture (views.py  → extract_text_from_base64)
  - RAG pipeline                 (rag_service.py → extract_text, extract_images_from_pptx/pdf)

All processing runs on-server (CPU or GPU).  No external API keys required.
"""

import io
import re
import base64
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_ocr_service_instance = None


def get_ocr_service():
    """Return the shared OCRService instance (lazy-initialised)."""
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = OCRService()
    return _ocr_service_instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pil_from_bytes(image_bytes: bytes) -> Image.Image:
    """Open raw bytes as a PIL Image converted to RGB."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _looks_garbled(text: str, threshold: float = 0.45) -> bool:
    """
    Return True if *text* looks like garbled OCR output — i.e. the
    recognition model failed to interpret math symbols correctly.

    Heuristic: if more than *threshold* of the non-whitespace characters
    are **not** alphanumeric and not common punctuation, assume it is math
    that was poorly decoded.
    """
    stripped = re.sub(r"\s+", "", text)
    if len(stripped) < 3:
        return False
    normal_chars = sum(
        1 for ch in stripped
        if ch.isalnum() or ch in ".,;:!?¿¡'\"-()[]{}/"
    )
    return (normal_chars / len(stripped)) < (1.0 - threshold)


def _texify_tags_to_latex(text: str) -> str:
    """
    Convert Surya/Texify ``<math>…</math>`` tags to standard LaTeX
    delimiters (``$$…$$`` for display, ``$…$`` for inline).
    """
    text = re.sub(r'<math\s+display="block">(.*?)</math>', r'$$\1$$', text, flags=re.DOTALL)
    text = re.sub(r'<math\s+display="inline">(.*?)</math>', r'$\1$', text, flags=re.DOTALL)
    text = re.sub(r'<math>(.*?)</math>', r'$\1$', text, flags=re.DOTALL)
    return text.strip()


# ---------------------------------------------------------------------------
# OCRService
# ---------------------------------------------------------------------------

class OCRService:
    """
    Reusable OCR module for Kairos.

    Memory-efficient: uses only RecognitionPredictor + DetectionPredictor
    (skips LayoutPredictor to avoid OOM on small droplets).

    Public API (stable — used by views.py & rag_service.py):
        extract_text(image_bytes)            → str
        extract_text_from_base64(b64_str)    → str
        extract_images_from_pptx(pptx_bytes) → list[dict]
        extract_images_from_pdf(pdf_bytes)   → list[dict]
    """

    def __init__(self):
        self._recognition_predictor = None
        self._detection_predictor = None
        self._foundation = None
        self._has_task_names = None  # cached import check

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _get_recognition(self):
        """Load Surya RecognitionPredictor + DetectionPredictor (shared foundation)."""
        if self._recognition_predictor is None:
            import gc
            from surya.recognition import RecognitionPredictor
            from surya.detection import DetectionPredictor
            from surya.foundation import FoundationPredictor

            logger.info("[OCR] Loading Surya models …")
            self._foundation = FoundationPredictor()
            self._recognition_predictor = RecognitionPredictor(self._foundation)
            self._detection_predictor = DetectionPredictor()
            gc.collect()
            logger.info("[OCR] Models ready")
        return self._recognition_predictor, self._detection_predictor

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ocr_text(self, img: Image.Image) -> str:
        """Run RecognitionPredictor on an image → plain text."""
        rec, det = self._get_recognition()
        preds = rec([img], det_predictor=det)
        if not preds:
            return ""
        lines = []
        for pred in preds:
            for line in getattr(pred, "text_lines", []):
                lines.append(line.text)
        return "\n".join(lines).strip()

    def _ocr_latex(self, img: Image.Image) -> str:
        """Run RecognitionPredictor in LaTeX mode → math notation."""
        if self._has_task_names is None:
            try:
                from surya.common.surya.schema import TaskNames  # noqa: F401
                self._has_task_names = True
            except ImportError:
                self._has_task_names = False

        if not self._has_task_names:
            return ""

        from surya.common.surya.schema import TaskNames
        rec, _ = self._get_recognition()
        preds = rec([img], tasks=[TaskNames.block_without_boxes])
        if not preds:
            return ""
        parts = []
        for pred in preds:
            for line in getattr(pred, "text_lines", []):
                parts.append(line.text)
        raw = "\n".join(parts).strip() if parts else ""
        if not raw:
            raw = getattr(preds[0], "text", "").strip()
        return _texify_tags_to_latex(raw) if raw else ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text(self, image_bytes: bytes, **kwargs) -> str:
        """
        Main entry point.  Returns extracted text with LaTeX for maths.

        Pipeline (memory-efficient):
          1. RecognitionPredictor extracts text from the full image.
          2. If output looks garbled (many non-alphanumeric chars),
             retry with LaTeX task (block_without_boxes).
          3. Return best result.

        Any extra **kwargs are accepted for backwards-compatibility but
        are ignored.
        """
        if not image_bytes:
            return ""

        try:
            img = _pil_from_bytes(image_bytes)
        except Exception as e:
            logger.error(f"[OCR] Cannot open image: {e}")
            return ""

        # First pass: plain text recognition
        text = self._ocr_text(img)

        if not text or _looks_garbled(text):
            # Likely math content → try LaTeX mode
            logger.info("[OCR] Text empty or garbled → trying LaTeX mode")
            latex = self._ocr_latex(img)
            if latex:
                return latex
            # If LaTeX mode also failed, return whatever we got
            return text or ""

        logger.info(f"[OCR] Extracted {len(text)} chars")
        return text

    def extract_text_from_base64(self, b64_string: str, **kwargs) -> str:
        """Accept a base64 data-URI or raw base64 string → extracted text."""
        if "," in b64_string and b64_string.startswith("data:"):
            b64_string = b64_string.split(",", 1)[1]
        try:
            raw = base64.b64decode(b64_string)
        except Exception as e:
            logger.error(f"[OCR] Invalid base64: {e}")
            return ""
        return self.extract_text(raw)

    # ------------------------------------------------------------------
    # PPTX image extraction
    # ------------------------------------------------------------------

    def extract_images_from_pptx(self, pptx_bytes: bytes) -> list[dict]:
        """
        Extract embedded images from a PPTX and OCR them.
        Returns ``[{'slide': int, 'text': str}, …]``.
        """
        results: list[dict] = []
        try:
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            prs = Presentation(io.BytesIO(pptx_bytes))
            for slide_num, slide in enumerate(prs.slides, 1):
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        try:
                            img_bytes = shape.image.blob
                            if len(img_bytes) < 5000:
                                continue
                            text = self.extract_text(img_bytes)
                            if text and len(text.strip()) > 20:
                                results.append({"slide": slide_num, "text": text.strip()})
                        except Exception as e:
                            logger.debug(f"[OCR-PPTX] Slide {slide_num} image error: {e}")
        except Exception as e:
            logger.error(f"[OCR-PPTX] Failed to process PPTX images: {e}")
        return results

    # ------------------------------------------------------------------
    # PDF image extraction
    # ------------------------------------------------------------------

    def extract_images_from_pdf(self, pdf_bytes: bytes) -> list[dict]:
        """
        Extract embedded images from a PDF and OCR them.
        Returns ``[{'page': int, 'text': str}, …]``.
        """
        results: list[dict] = []
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if not page.images:
                        continue
                    try:
                        pil_img = page.to_image(resolution=200).original
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        text = self.extract_text(buf.getvalue())
                        if text and len(text.strip()) > 20:
                            results.append({"page": page_num, "text": text.strip()})
                    except Exception as e:
                        logger.debug(f"[OCR-PDF] Page {page_num} render error: {e}")
        except Exception as e:
            logger.error(f"[OCR-PDF] Failed to process PDF images: {e}")
        return results
