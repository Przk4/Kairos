"""
Kairos OCR Service — Image-to-text extraction with math formula support.

Primary:   GPT-4o-mini vision API (best for math formulas, tables, diagrams)
Fallback:  pytesseract local OCR

Used by:
  - Chat image uploads
  - Extension screenshot capture
  - RAG pipeline (image files from Canvas, images embedded in PPTX/PDF)
"""

import os
import io
import re
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_ocr_service_instance = None


def get_ocr_service():
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = OCRService()
    return _ocr_service_instance


class OCRService:
    """Extracts text (including LaTeX math, tables, code) from images."""

    VISION_SYSTEM_PROMPT = (
        "You are an expert OCR assistant specialised in academic content. "
        "Extract ALL text from the image accurately.\n\n"
        "Rules:\n"
        "- Wrap math formulas in LaTeX: inline $...$ or display $$...$$\n"
        "- Reproduce tables as Markdown pipe tables\n"
        "- Keep original language (Spanish / English)\n"
        "- Preserve numbered lists, bullet points, headings\n"
        "- If there is a graph or diagram, describe it briefly\n"
        "- Output ONLY the extracted content, no commentary"
    )

    def __init__(self):
        self.openai_client = None
        self.vision_model = "gpt-4o-mini"
        self._init_openai()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _init_openai(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            logger.warning("[OCR] OPENAI_API_KEY not set — vision OCR unavailable, will use fallback")
            return
        try:
            import openai
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.info("[OCR] GPT-4o-mini vision initialised")
        except Exception as e:
            logger.error(f"[OCR] Failed to init OpenAI client: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_text(self, image_bytes: bytes, *, detail: str = "high") -> str:
        """
        Main entry point.  Returns extracted text (with LaTeX for math).
        *detail*: 'low' | 'high' | 'auto' — controls GPT-4o-mini resolution.
        """
        if not image_bytes:
            return ""

        # Try vision LLM first
        if self.openai_client:
            result = self._extract_with_vision(image_bytes, detail=detail)
            if result:
                return result

        # Fallback: pytesseract
        result = self._extract_with_tesseract(image_bytes)
        if result:
            return result

        logger.warning("[OCR] All extraction methods failed")
        return ""

    def extract_text_from_base64(self, b64_string: str, *, detail: str = "high") -> str:
        """Convenience: accept a base64 data-URI or raw b64 string."""
        # Strip data URI prefix if present
        if "," in b64_string and b64_string.startswith("data:"):
            b64_string = b64_string.split(",", 1)[1]
        try:
            raw = base64.b64decode(b64_string)
        except Exception as e:
            logger.error(f"[OCR] Invalid base64: {e}")
            return ""
        return self.extract_text(raw, detail=detail)

    # ------------------------------------------------------------------
    # GPT-4o-mini vision
    # ------------------------------------------------------------------
    def _extract_with_vision(self, image_bytes: bytes, *, detail: str = "high") -> Optional[str]:
        try:
            b64 = base64.b64encode(image_bytes).decode()

            # Detect MIME type
            mime = "image/png"
            if image_bytes[:3] == b'\xff\xd8\xff':
                mime = "image/jpeg"
            elif image_bytes[:4] == b'\x89PNG':
                mime = "image/png"
            elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
                mime = "image/webp"

            data_uri = f"data:{mime};base64,{b64}"

            response = self.openai_client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": self.VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_uri, "detail": detail},
                            },
                            {
                                "type": "text",
                                "text": "Extract all text, math formulas (as LaTeX), and tables from this image.",
                            },
                        ],
                    },
                ],
                max_tokens=4096,
                temperature=0.1,
            )

            text = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            logger.info(f"[OCR-Vision] Extracted {len(text)} chars, {tokens} tokens")
            return text.strip()

        except Exception as e:
            logger.error(f"[OCR-Vision] Error: {e}")
            return None

    # ------------------------------------------------------------------
    # Tesseract fallback
    # ------------------------------------------------------------------
    def _extract_with_tesseract(self, image_bytes: bytes) -> Optional[str]:
        try:
            from PIL import Image, ImageFilter, ImageEnhance
            import pytesseract
        except ImportError:
            logger.info("[OCR-Tesseract] pytesseract or Pillow not installed — skipping")
            return None

        try:
            img = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if needed
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = bg

            # Pre-processing: enhance contrast, sharpen
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img = img.filter(ImageFilter.SHARPEN)

            # OCR — Spanish + English
            text = pytesseract.image_to_string(img, lang="spa+eng", config="--psm 6")
            text = text.strip()
            if text:
                logger.info(f"[OCR-Tesseract] Extracted {len(text)} chars")
            return text or None

        except Exception as e:
            logger.error(f"[OCR-Tesseract] Error: {e}")
            return None

    # ------------------------------------------------------------------
    # PPTX image extraction helper
    # ------------------------------------------------------------------
    def extract_images_from_pptx(self, pptx_bytes: bytes) -> list[dict]:
        """
        Extract embedded images from a PPTX file.
        Returns list of {'slide': int, 'text': str} for images that contain
        readable text (diagrams, formulas, screenshots of text).
        """
        results = []
        try:
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            prs = Presentation(io.BytesIO(pptx_bytes))
            for slide_num, slide in enumerate(prs.slides, 1):
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        try:
                            img_bytes = shape.image.blob
                            # Skip tiny images (icons, bullets)
                            if len(img_bytes) < 5000:
                                continue
                            text = self.extract_text(img_bytes, detail="high")
                            if text and len(text.strip()) > 20:
                                results.append({
                                    "slide": slide_num,
                                    "text": text.strip(),
                                })
                        except Exception as e:
                            logger.debug(f"[OCR-PPTX] Slide {slide_num} image error: {e}")
        except Exception as e:
            logger.error(f"[OCR-PPTX] Failed to process PPTX images: {e}")
        return results

    # ------------------------------------------------------------------
    # PDF image extraction helper
    # ------------------------------------------------------------------
    def extract_images_from_pdf(self, pdf_bytes: bytes) -> list[dict]:
        """
        Extract embedded images from a PDF and OCR them.
        Returns list of {'page': int, 'text': str}.
        """
        results = []
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    images = page.images
                    if not images:
                        continue
                    # Render page as image and OCR it if it has images
                    # This captures diagrams, formulas, figures
                    try:
                        pil_img = page.to_image(resolution=200).original
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        img_bytes = buf.getvalue()
                        text = self.extract_text(img_bytes, detail="high")
                        if text and len(text.strip()) > 20:
                            results.append({
                                "page": page_num,
                                "text": text.strip(),
                            })
                    except Exception as e:
                        logger.debug(f"[OCR-PDF] Page {page_num} render error: {e}")
        except Exception as e:
            logger.error(f"[OCR-PDF] Failed to process PDF images: {e}")
        return results
