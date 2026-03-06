"""
Kairos OCR Service — Image-to-text extraction with math formula support.

Engine:  Surya OCR  (local, no external API calls)
  - RecognitionPredictor  → general text (printed documents)
  - TexifyPredictor       → math formulas / equations → LaTeX output

Used by:
  - Chat image uploads          (views.py  → extract_text / extract_text_from_base64)
  - Extension screenshot capture (views.py  → extract_text_from_base64)
  - RAG pipeline                 (rag_service.py → extract_text, extract_images_from_pptx/pdf)

All processing runs on-server (CPU or GPU). No external API keys required.
"""

import io
import base64
import logging
from typing import Optional

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


def _has_math(text: str) -> bool:
    """Quick heuristic: does *text* look like it contains math symbols?"""
    math_indicators = {
        "∫", "∑", "∏", "√", "∞", "≠", "≤", "≥", "±", "∈", "∉",
        "⊂", "⊃", "∪", "∩", "∀", "∃", "∂", "∇", "⊕", "⊗",
        "α", "β", "γ", "δ", "θ", "λ", "μ", "σ", "φ", "ω",
        "Σ", "Π", "Δ", "Ω",
    }
    if any(ch in text for ch in math_indicators):
        return True
    # Common LaTeX-ish fragments that Surya may partially recognise
    import re
    return bool(re.search(
        r"\\frac|\\int|\\sum|\\sqrt|\\lim|\\alpha|\\beta|\\theta|\\sigma"
        r"|\\begin\{|\\end\{|\^\{|_\{",
        text,
    ))


# ---------------------------------------------------------------------------
# OCRService
# ---------------------------------------------------------------------------

class OCRService:
    """
    Reusable OCR module for Kairos.

    Public API (stable — used by views.py & rag_service.py):
        extract_text(image_bytes)          → str
        extract_text_from_base64(b64_str)  → str
        extract_images_from_pptx(pptx_bytes) → list[dict]
        extract_images_from_pdf(pdf_bytes)   → list[dict]
    """

    def __init__(self):
        # Predictors are loaded lazily on first use to avoid slow import
        # at Django startup and to keep memory footprint low when OCR is
        # not needed.
        self._recognition_predictor = None
        self._detection_predictor = None
        self._texify_predictor = None
        self._foundation_predictor = None

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _get_recognition(self):
        """Load Surya recognition + detection predictors on first call."""
        if self._recognition_predictor is None:
            from surya.recognition import RecognitionPredictor
            from surya.detection import DetectionPredictor
            from surya.foundation import FoundationPredictor

            logger.info("[OCR] Loading Surya recognition models …")
            self._foundation_predictor = FoundationPredictor()
            self._recognition_predictor = RecognitionPredictor(self._foundation_predictor)
            self._detection_predictor = DetectionPredictor()
            logger.info("[OCR] Surya recognition models ready")
        return self._recognition_predictor, self._detection_predictor

    def _get_texify(self):
        """Load Surya TexifyPredictor (LaTeX OCR) on first call."""
        if self._texify_predictor is None:
            from surya.texify import TexifyPredictor

            logger.info("[OCR] Loading Surya TexifyPredictor (LaTeX) …")
            self._texify_predictor = TexifyPredictor()
            logger.info("[OCR] TexifyPredictor ready")
        return self._texify_predictor

    # ------------------------------------------------------------------
    # Internal extraction
    # ------------------------------------------------------------------

    def _surya_ocr(self, img: Image.Image) -> str:
        """Run Surya general OCR on a single PIL image → plain text."""
        rec, det = self._get_recognition()
        predictions = rec([img], det_predictor=det)
        if not predictions:
            return ""
        lines = []
        for pred in predictions:
            for line in getattr(pred, "text_lines", []):
                lines.append(line.text)
        return "\n".join(lines).strip()

    def _surya_latex(self, img: Image.Image) -> str:
        """Run TexifyPredictor on a single PIL image → LaTeX string."""
        texify = self._get_texify()
        results = texify([img])
        if not results:
            return ""
        # results is a list (one per image); each item has .text
        return results[0].text.strip() if hasattr(results[0], "text") else str(results[0]).strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text(self, image_bytes: bytes, **kwargs) -> str:
        """
        Main entry point.  Returns extracted text.

        1. Run Surya general OCR.
        2. If the result contains math symbols / partial formulas,
           also run TexifyPredictor on the full image and merge
           the LaTeX output into the response.

        Any extra **kwargs (e.g. ``detail``) are accepted for
        backwards-compatibility but ignored (Surya doesn't need them).
        """
        if not image_bytes:
            return ""

        try:
            img = _pil_from_bytes(image_bytes)
        except Exception as e:
            logger.error(f"[OCR] Cannot open image: {e}")
            return ""

        # Step 1 — general OCR
        text = self._surya_ocr(img)
        logger.info(f"[OCR-Surya] Extracted {len(text)} chars")

        # Step 2 — if math detected, run TexifyPredictor for LaTeX
        if text and _has_math(text):
            try:
                latex = self._surya_latex(img)
                if latex:
                    logger.info(f"[OCR-Texify] LaTeX extracted ({len(latex)} chars)")
                    # Append LaTeX block so downstream consumers
                    # (chat, embeddings) get both plain text and formulas.
                    text = f"{text}\n\n$$\n{latex}\n$$"
            except Exception as e:
                logger.warning(f"[OCR-Texify] LaTeX extraction failed: {e}")

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
