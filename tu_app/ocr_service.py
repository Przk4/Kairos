"""
Kairos OCR Service — Image-to-text extraction with math formula support.

Engine:  Surya OCR  (local, no external API calls)
  - LayoutPredictor       → detect regions (Text vs Equation)
  - RecognitionPredictor  → general text for Text regions
  - RecognitionPredictor  → LaTeX for Equation regions (TaskNames.block_without_boxes)

Pipeline:
  1. LayoutPredictor segments the image into regions.
  2. Regions labelled "Equation" are cropped and sent to TexifyPredictor
     to produce LaTeX (wrapped in $$ delimiters).
  3. Other regions are cropped and sent to RecognitionPredictor for
     plain-text OCR.
  4. Fallback: if RecognitionPredictor output looks garbled (high ratio
     of non-alphanumeric characters), the region is re-processed with
     TexifyPredictor.
  5. All fragments are assembled in reading order.

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


# Labels that LayoutPredictor assigns to math / equation regions.
_EQUATION_LABELS = {"Equation", "Formula", "TextInlineMath"}


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

    Public API (stable — used by views.py & rag_service.py):
        extract_text(image_bytes)            → str
        extract_text_from_base64(b64_str)    → str
        extract_images_from_pptx(pptx_bytes) → list[dict]
        extract_images_from_pdf(pdf_bytes)   → list[dict]
    """

    def __init__(self):
        # All predictors are loaded lazily to avoid slow imports at
        # Django startup and to keep memory low when OCR is unused.
        self._layout_predictor = None
        self._layout_foundation = None
        self._recognition_predictor = None
        self._detection_predictor = None
        self._recognition_foundation = None

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _get_layout(self):
        """Load Surya LayoutPredictor on first call."""
        if self._layout_predictor is None:
            from surya.layout import LayoutPredictor
            from surya.foundation import FoundationPredictor

            logger.info("[OCR] Loading Surya LayoutPredictor …")
            self._layout_foundation = FoundationPredictor()
            self._layout_predictor = LayoutPredictor(self._layout_foundation)
            logger.info("[OCR] LayoutPredictor ready")
        return self._layout_predictor

    def _get_recognition(self):
        """Load Surya RecognitionPredictor + DetectionPredictor."""
        if self._recognition_predictor is None:
            from surya.recognition import RecognitionPredictor
            from surya.detection import DetectionPredictor
            from surya.foundation import FoundationPredictor

            logger.info("[OCR] Loading Surya recognition models …")
            self._recognition_foundation = FoundationPredictor()
            self._recognition_predictor = RecognitionPredictor(self._recognition_foundation)
            self._detection_predictor = DetectionPredictor()
            logger.info("[OCR] Recognition models ready")
        return self._recognition_predictor, self._detection_predictor

    # ------------------------------------------------------------------
    # Internal: per-region extraction
    # ------------------------------------------------------------------

    def _ocr_text_region(self, img: Image.Image) -> str:
        """Run RecognitionPredictor on a cropped text region."""
        rec, det = self._get_recognition()
        preds = rec([img], det_predictor=det)
        if not preds:
            return ""
        lines = []
        for pred in preds:
            for line in getattr(pred, "text_lines", []):
                lines.append(line.text)
        return "\n".join(lines).strip()

    def _ocr_equation_region(self, img: Image.Image) -> str:
        """Run RecognitionPredictor in LaTeX mode (TaskNames.block_without_boxes)."""
        try:
            from surya.common.surya.schema import TaskNames
        except ImportError:
            logger.warning("[OCR] TaskNames not available; falling back to text OCR for equation")
            return self._ocr_text_region(img)

        rec, _ = self._get_recognition()
        tasks = [TaskNames.block_without_boxes]
        preds = rec([img], tasks)
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

        Pipeline:
          1. LayoutPredictor segments the image into labelled regions.
          2. Equation regions → TexifyPredictor → LaTeX ($$…$$).
          3. Text regions → RecognitionPredictor → plain text.
             - If OCR output looks garbled, retry with TexifyPredictor.
          4. Assemble fragments in reading order.

        Any extra **kwargs are accepted for backwards-compatibility but
        are ignored (Surya does not need them).
        """
        if not image_bytes:
            return ""

        try:
            img = _pil_from_bytes(image_bytes)
        except Exception as e:
            logger.error(f"[OCR] Cannot open image: {e}")
            return ""

        # ----- Step 1: Layout detection -----
        try:
            layout = self._get_layout()
            layout_results = layout([img])
            boxes = layout_results[0].bboxes if layout_results else []
        except Exception as e:
            logger.warning(f"[OCR] Layout detection failed, falling back to full-image OCR: {e}")
            boxes = []

        # If layout found no regions, treat the whole image as one region
        if not boxes:
            text = self._ocr_text_region(img)
            if _looks_garbled(text):
                logger.info("[OCR] Full-image OCR looks garbled → trying TexifyPredictor")
                latex = self._ocr_equation_region(img)
                return latex if latex else text
            return text

        # ----- Step 2 & 3: Process each region in reading order -----
        sorted_boxes = sorted(boxes, key=lambda b: b.position)
        fragments: list[str] = []

        for box in sorted_boxes:
            label = box.label
            bbox = box.bbox  # [x_min, y_min, x_max, y_max]

            # Crop with a small padding to avoid cutting edges
            pad = 4
            x0 = max(0, int(bbox[0]) - pad)
            y0 = max(0, int(bbox[1]) - pad)
            x1 = min(img.width, int(bbox[2]) + pad)
            y1 = min(img.height, int(bbox[3]) + pad)
            cropped = img.crop((x0, y0, x1, y1))

            if cropped.width < 10 or cropped.height < 10:
                continue

            if label in _EQUATION_LABELS:
                # ---- Equation region → TexifyPredictor ----
                latex = self._ocr_equation_region(cropped)
                if latex:
                    # Wrap in display-math delimiters if not already wrapped
                    if not latex.startswith("$"):
                        latex = f"$${latex}$$"
                    fragments.append(latex)
                    logger.debug(f"[OCR] Equation region ({label}): {len(latex)} chars")
            else:
                # ---- Text region → RecognitionPredictor ----
                text = self._ocr_text_region(cropped)
                if text and _looks_garbled(text):
                    # Garbled output → likely undetected math; retry
                    logger.info(f"[OCR] Region '{label}' looks garbled → retrying with Texify")
                    latex = self._ocr_equation_region(cropped)
                    if latex:
                        if not latex.startswith("$"):
                            latex = f"$${latex}$$"
                        fragments.append(latex)
                        continue
                if text:
                    fragments.append(text)
                    logger.debug(f"[OCR] Text region ({label}): {len(text)} chars")

        result = "\n\n".join(fragments).strip()
        logger.info(f"[OCR] Total extracted: {len(result)} chars from {len(sorted_boxes)} regions")
        return result

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
