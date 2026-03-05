# tu_app/rag_service.py

import os
import json
import logging
import warnings
import time
import pickle
import re
from pathlib import Path
from typing import List, Optional
import numpy as np
import requests
from django.conf import settings
from sentence_transformers import SentenceTransformer
from tu_app.debug_service import get_debug_service

logger = logging.getLogger(__name__)

# Suppress Pydantic v1 warnings from chromadb before import
warnings.filterwarnings('ignore', message='Core Pydantic V1 functionality')
warnings.filterwarnings('ignore', category=UserWarning)

# Import chromadb with proper error handling
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
    logger.info("ChromaDB imported successfully")
except ImportError as e:
    logger.error(f"ChromaDB not available: {e}")
    CHROMADB_AVAILABLE = False
    chromadb = None
except Exception as e:
    logger.error(f"ChromaDB initialization error: {e}")
    CHROMADB_AVAILABLE = False
    chromadb = None

# Intentar importar pdfplumber para lectura de PDFs
try:
    import pdfplumber
    PDF_READER_AVAILABLE = True
    logger.info("pdfplumber imported successfully for PDF processing")
except ImportError:
    logger.warning("pdfplumber not available - PDF processing will be limited")
    PDF_READER_AVAILABLE = False
    pdfplumber = None

# Importar librerías para otros formatos de documentos
try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
    logger.info("python-pptx imported successfully for PPTX processing")
except ImportError:
    logger.warning("python-pptx not available - PPTX processing will be disabled")
    PPTX_AVAILABLE = False
    Presentation = None

try:
    from docx import Document
    DOCX_AVAILABLE = True
    logger.info("python-docx imported successfully for DOCX processing")
except ImportError:
    logger.warning("python-docx not available - DOCX processing will be disabled")
    DOCX_AVAILABLE = False
    Document = None

try:
    from openpyxl import load_workbook
    XLSX_AVAILABLE = True
    logger.info("openpyxl imported successfully for XLSX processing")
except ImportError:
    logger.warning("openpyxl not available - XLSX processing will be disabled")
    XLSX_AVAILABLE = False
    load_workbook = None


class RAGService:
    """
    Servicio de RAG con Piragi para análisis de módulos de Canvas.
    Preparado para ser escalable a la nube (cloud-agnostic).
    
    NOTA: Si ChromaDB no está disponible, usa una versión simplificada en memoria.
    """
    
    def __init__(self, persistent_dir: Optional[str] = None):
        """
        Inicializa el servicio de RAG.
        
        Args:
            persistent_dir: Directorio para ChromaDB. Si es None, usa directorio por defecto.
        """
        self.persistent_dir = persistent_dir or os.path.join(settings.BASE_DIR, '.chroma_db')
        Path(self.persistent_dir).mkdir(exist_ok=True)
        
        # Directorio para almacenamiento de JSON (fallback cuando no hay ChromaDB)
        self.json_embeddings_dir = os.path.join(settings.BASE_DIR, '.embeddings')
        Path(self.json_embeddings_dir).mkdir(exist_ok=True)
        
        # Modelo de embeddings
        self.embedding_model = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2'
        )
        
        # En memoria: almacenar documentos por módulo
        self.in_memory_db = {}
        
        # Cargar embeddings guardados en JSON si existen
        self._load_json_embeddings()
        
        if CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=self.persistent_dir)
                logger.info(f"ChromaDB PersistentClient initialized at: {self.persistent_dir}")
                self.using_chromadb = True
            except Exception as e:
                logger.warning(f"ChromaDB initialization failed, using in-memory storage: {e}")
                self.client = None
                self.using_chromadb = False
        else:
            logger.warning("ChromaDB not available, using in-memory storage for RAG")
            self.client = None
            self.using_chromadb = False
        
        logger.info(f"RAG Service initialized - Using ChromaDB: {self.using_chromadb}, PDF Reader: {PDF_READER_AVAILABLE}")
    
    def _load_json_embeddings(self):
        """Cargar embeddings guardados en JSON al iniciar"""
        try:
            for json_file in Path(self.json_embeddings_dir).glob('*.json'):
                collection_name = json_file.stem
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.in_memory_db[collection_name] = data
                    logger.info(f"Loaded {len(data.get('documents', []))} documents from {json_file.name}")
        except Exception as e:
            logger.warning(f"Could not load JSON embeddings: {e}")
    
    def _save_json_embeddings(self, collection_name: str, data: dict):
        """Guardar embeddings en JSON para persistencia"""
        try:
            json_path = os.path.join(self.json_embeddings_dir, f"{collection_name}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved embeddings to {json_path}")
        except Exception as e:
            logger.error(f"Error saving JSON embeddings: {e}")
    
    def _extract_text_from_pdf(self, pdf_bytes) -> str:
        """
        Extrae texto de un PDF usando pdfplumber.
        Fallback si pdfplumber no está disponible.
        """
        if not PDF_READER_AVAILABLE:
            logger.warning("pdfplumber not available, returning placeholder")
            return "[PDF Document - Text extraction not available]"
        
        try:
            import io
            logger.info(f"Attempting to extract PDF with pdfplumber, PDF size: {len(pdf_bytes)} bytes")
            
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                logger.info(f"PDF opened successfully, total pages: {len(pdf.pages)}")
                text = ""
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        logger.info(f"Page {page_num + 1}: extracted {len(page_text)} chars")
                        text += f"\n--- Página {page_num + 1} ---\n{page_text}"
                    else:
                        logger.warning(f"Page {page_num + 1}: no text extracted")
                
                final_text = text if text.strip() else "[PDF vacío o no legible]"
                logger.info(f"PDF extraction complete: total {len(final_text)} chars extracted")
                return final_text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}", exc_info=True)
            return f"[Error leyendo PDF: {str(e)[:100]}]"
    
    # Patrones de ruido PPTX a eliminar (compilados una vez)
    _NOISE_PATTERNS = [
        re.compile(r'^\d{1,3}$'),                                          # Solo números (slide/página)
        re.compile(r'^20[\dXx]{2}$'),                                      # "20XX", "2026", etc. solos
        re.compile(r'^20[\dXx]{2}\s+', re.IGNORECASE),                     # "20XX Algo..." al inicio
        re.compile(r'pie de p[aá]gina', re.IGNORECASE),                    # Cualquier mención de pie de página
        re.compile(r'ejemplo de texto', re.IGNORECASE),                    # Template placeholder text
        re.compile(r'^(?:©|\(c\)|copyright)\s*20', re.IGNORECASE),         # Copyright lines
        re.compile(r'^footer\b', re.IGNORECASE),                           # Footer labels
        re.compile(r'^(click to edit|haga clic|insert|placeholder)', re.IGNORECASE),  # Template instructions
        re.compile(r'^(slide|diapositiva)\s*\d', re.IGNORECASE),           # "Slide 1" labels
        re.compile(r'^\*+$'),                                              # Lines of only asterisks
    ]

    def _clean_slide_text(self, text: str) -> str:
        """
        Limpia texto extraído de un slide eliminando ruido típico de PPTX.
        """
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Eliminar líneas demasiado cortas que no aportan (< 3 chars)
            if len(line) < 3:
                continue
            
            # Verificar contra todos los patrones de ruido
            is_noise = False
            for pattern in self._NOISE_PATTERNS:
                if pattern.search(line):
                    is_noise = True
                    break
            if is_noise:
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _table_to_markdown(self, table) -> str:
        """
        Convierte una tabla de python-pptx a formato Markdown.
        """
        rows_data = []
        for row in table.rows:
            cells = [cell.text.strip().replace('|', '/') for cell in row.cells]
            rows_data.append(cells)
        
        if not rows_data:
            return ""
        
        # Normalizar: todas las filas deben tener el mismo número de columnas
        max_cols = max(len(r) for r in rows_data)
        for r in rows_data:
            while len(r) < max_cols:
                r.append('')
        
        # Construir Markdown table
        md_lines = []
        # Header (primera fila)
        md_lines.append('| ' + ' | '.join(rows_data[0]) + ' |')
        md_lines.append('| ' + ' | '.join(['---'] * max_cols) + ' |')
        # Resto de filas
        for row in rows_data[1:]:
            md_lines.append('| ' + ' | '.join(row) + ' |')
        
        return '\n'.join(md_lines)

    def _extract_text_from_pptx(self, pptx_bytes) -> Optional[str]:
        """
        Extrae texto de un archivo PPTX (PowerPoint).
        Agrupa contenido por slide con título semántico en lugar de marcadores numéricos.
        Limpia ruido (footers, números sueltos, contenido vacío).
        """
        if not PPTX_AVAILABLE:
            logger.warning("python-pptx not available, returning None for PPTX file")
            return None
        
        try:
            import io
            logger.info(f"Attempting to extract PPTX with python-pptx, file size: {len(pptx_bytes)} bytes")
            
            presentation = Presentation(io.BytesIO(pptx_bytes))
            logger.info(f"PPTX opened successfully, total slides: {len(presentation.slides)}")
            
            all_slide_texts = []
            skipped_slides = 0
            self._last_pptx_tables = []  # Almacenar tablas extraídas para embeddings separados
            
            for slide_num, slide in enumerate(presentation.slides):
                slide_title = ""
                body_parts = []
                
                for shape in slide.shapes:
                    try:
                        # Extraer texto del shape
                        shape_text = ""
                        try:
                            if hasattr(shape, 'text') and shape.text:
                                shape_text = shape.text.strip()
                        except Exception:
                            pass
                        
                        # Detectar si es título del slide (placeholder idx 0 o 1)
                        is_title = False
                        try:
                            if hasattr(shape, 'placeholder_format') and shape.placeholder_format is not None:
                                if shape.placeholder_format.idx in (0, 1):
                                    is_title = True
                        except Exception:
                            pass
                        
                        # Si es una tabla, convertir a Markdown
                        is_table = False
                        try:
                            if shape.shape_type == 14:  # MSO_SHAPE_TYPE.TABLE
                                is_table = True
                                md_table = self._table_to_markdown(shape.table)
                                if md_table and len(md_table) > 10:
                                    body_parts.append(md_table)
                                    # Guardar tabla con contexto del slide para embedding separado
                                    table_context = slide_title or f"Slide {slide_num + 1}"
                                    self._last_pptx_tables.append({
                                        'slide_num': slide_num + 1,
                                        'slide_title': table_context,
                                        'markdown': md_table,
                                        'row_count': len(shape.table.rows),
                                        'col_count': len(shape.table.columns) if hasattr(shape.table, 'columns') else 0,
                                    })
                                    logger.info(f"  [TABLE] Slide {slide_num + 1}: {len(shape.table.rows)} rows Markdown table")
                        except Exception:
                            pass
                        
                        # Agregar texto (si no es tabla, porque la tabla ya se agregó como Markdown)
                        if shape_text and not is_table:
                            if is_title and not slide_title:
                                slide_title = shape_text
                            else:
                                body_parts.append(shape_text)
                    except Exception as e:
                        logger.warning(f"Error processing shape in slide {slide_num + 1}: {e}")
                        continue
                
                # Combinar y limpiar el contenido del slide
                raw_body = '\n'.join(body_parts)
                clean_body = self._clean_slide_text(raw_body)
                clean_title = self._clean_slide_text(slide_title)
                
                # Solo incluir slides con contenido significativo (> 10 chars)
                total_content = f"{clean_title} {clean_body}".strip()
                if len(total_content) < 10:
                    skipped_slides += 1
                    continue
                
                # Formato: usar título del slide como encabezado semántico
                if clean_title:
                    slide_block = f"\n{clean_title}\n{clean_body}" if clean_body else f"\n{clean_title}"
                else:
                    slide_block = f"\n{clean_body}"
                
                all_slide_texts.append(slide_block)
            
            if not all_slide_texts:
                return "[PPTX vacío o sin contenido de texto]"
            
            final_text = '\n'.join(all_slide_texts)
            logger.info(f"PPTX extraction complete: {len(all_slide_texts)} slides with content, "
                       f"{skipped_slides} skipped, {len(self._last_pptx_tables)} tables found, "
                       f"{len(final_text)} chars total")
            return final_text
        except Exception as e:
            logger.error(f"Error extracting PPTX text: {e}", exc_info=True)
            return None
    
    def _extract_text_from_docx(self, docx_bytes) -> Optional[str]:
        """
        Extrae texto de un archivo DOCX (Word).
        Incluye párrafos, tablas y listas.
        """
        if not DOCX_AVAILABLE:
            logger.warning("python-docx not available, returning None for DOCX file")
            return None
        
        try:
            import io
            logger.info(f"Attempting to extract DOCX with python-docx, file size: {len(docx_bytes)} bytes")
            
            document = Document(io.BytesIO(docx_bytes))
            logger.info(f"DOCX opened successfully, total paragraphs: {len(document.paragraphs)}")
            
            text = ""
            
            # Extraer párrafos
            for para_num, paragraph in enumerate(document.paragraphs):
                para_text = paragraph.text.strip()
                if para_text:
                    text += para_text + "\n"
            
            # Extraer tablas
            for table_num, table in enumerate(document.tables):
                logger.info(f"Processing table {table_num + 1} with {len(table.rows)} rows")
                table_text = f"\n--- Tabla {table_num + 1} ---\n"
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        table_text += " | ".join(row_text) + "\n"
                text += table_text
            
            final_text = text if text.strip() else "[DOCX vacío o sin contenido]"
            logger.info(f"DOCX extraction complete: total {len(final_text)} chars extracted")
            return final_text
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}", exc_info=True)
            return None
    
    def _extract_text_from_xlsx(self, xlsx_bytes) -> Optional[str]:
        """
        Extrae texto de un archivo XLSX (Excel).
        Incluye todas las celdas con contenido.
        """
        if not XLSX_AVAILABLE:
            logger.warning("openpyxl not available, returning None for XLSX file")
            return None
        
        try:
            import io
            logger.info(f"Attempting to extract XLSX with openpyxl, file size: {len(xlsx_bytes)} bytes")
            
            workbook = load_workbook(io.BytesIO(xlsx_bytes))
            logger.info(f"XLSX opened successfully, total sheets: {len(workbook.sheetnames)}")
            
            text = ""
            for sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                logger.info(f"Processing sheet: {sheet_name}")
                
                text += f"\n--- Sheet: {sheet_name} ---\n"
                
                for row in worksheet.iter_rows(values_only=True):
                    row_text = []
                    for cell_value in row:
                        if cell_value is not None:
                            row_text.append(str(cell_value).strip())
                    if row_text:
                        text += " | ".join(row_text) + "\n"
            
            final_text = text if text.strip() else "[XLSX vacío o sin contenido]"
            logger.info(f"XLSX extraction complete: total {len(final_text)} chars extracted")
            return final_text
        except Exception as e:
            logger.error(f"Error extracting XLSX text: {e}", exc_info=True)
            return None
    
    def _extract_text_from_file(self, file_url: str, access_token: str) -> Optional[str]:
        """
        Descarga y extrae texto de archivos de Canvas.
        Canvas requiere autenticación con Bearer token para descargar archivos.
        Si ngrok falla, intenta con localhost.
        """
        try:
            logger.info(f"[FILE DOWNLOAD] Starting: {file_url}")
            
            # Canvas bloquea sin headers. Necesitamos User-Agent válido
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate',
            }
            
            # CRITICAL: Canvas requiere Authorization header para descargas de archivos
            # Aunque sea una URL pública, Canvas redirige a login si no hay token
            if access_token:
                headers['Authorization'] = f'Bearer {access_token}'
                logger.info(f"[FILE DOWNLOAD] ✓ Added Bearer token for authentication")
            else:
                logger.warning(f"[FILE DOWNLOAD] ⚠ No access token provided - Canvas may reject request")
            
            # Si es Canvas API /files/{id}, asegurar que tiene /download
            url_to_request = file_url
            if '/api/v1/files/' in file_url and '/download' not in file_url:
                url_to_request = f"{file_url}/download"
                logger.info(f"[FILE DOWNLOAD] Added /download: {url_to_request}")
            
            logger.info(f"[FILE DOWNLOAD] Making request with headers: {list(headers.keys())}")
            
            # Intentar descargar
            response = requests.get(
                url_to_request, 
                headers=headers, 
                timeout=60, 
                allow_redirects=True,
                verify=False  # NgRok SSL
            )
            
            logger.info(f"[FILE DOWNLOAD] Response {response.status_code}, {len(response.content)} bytes, Content-Type: {response.headers.get('content-type', '?')}")
            
            if response.status_code != 200:
                logger.error(f"[FILE DOWNLOAD] ❌ HTTP {response.status_code}")
                return None
            
            file_content = response.content
            
            # Si recibimos HTML en lugar de archivo
            if file_content.startswith(b'<!DOCTYPE') or file_content.startswith(b'<html'):
                logger.warning(f"[FILE DOWNLOAD] ⚠ Got HTML (possibly ngrok issue), trying with localhost...")
                
                # Intentar reemplazar ngrok domain con localhost
                if 'ngrok' in url_to_request:
                    localhost_url = url_to_request.replace(
                        url_to_request.split('/courses')[0],  # Reemplaza el dominio
                        'http://127.0.0.1:3000'
                    )
                    logger.info(f"[FILE DOWNLOAD] Retrying with localhost: {localhost_url[:80]}...")
                    
                    response = requests.get(
                        localhost_url,
                        headers=headers,
                        timeout=60,
                        allow_redirects=True,
                        verify=False
                    )
                    
                    file_content = response.content
                    logger.info(f"[FILE DOWNLOAD] Localhost response: {len(file_content)} bytes, Content-Type: {response.headers.get('content-type', '?')}")
                    
                    # Verificar nuevamente
                    if file_content.startswith(b'<!DOCTYPE') or file_content.startswith(b'<html'):
                        logger.error(f"[FILE DOWNLOAD] ❌ Still HTML on localhost - giving up")
                        return None
                else:
                    logger.error(f"[FILE DOWNLOAD] ❌ Got HTML instead of file! First 500 chars:")
                    logger.error(file_content[:500].decode('utf-8', errors='ignore'))
                    return None
            
            # Procesar según tipo de archivo
            # Primero intenta por extensión de URL, luego por Content-Type si no tiene extensión clara
            file_lower = file_url.lower()
            content_type = response.headers.get('content-type', '').lower()
            
            logger.info(f"[FILE TYPE DETECTION] URL ends with: ...{file_url[-50:]}, Content-Type: {content_type[:80] if content_type else 'unknown'}")
            
            if file_lower.endswith('.pdf') or 'application/pdf' in content_type:
                logger.info(f"[PDF PROCESSING] Extracting PDF with pdfplumber...")
                text = self._extract_text_from_pdf(file_content)
                if text and text.strip() and not text.startswith('['):
                    logger.info(f"[PDF PROCESSING] ✅ {len(text)} chars extracted")
                    return text
                else:
                    logger.error(f"[PDF PROCESSING] ❌ Failed to extract readable text from PDF")
                    return None
            
            elif file_lower.endswith(('.pptx', '.ppt')) or 'presentation' in content_type:
                logger.info(f"[PPTX PROCESSING] Extracting PowerPoint with python-pptx...")
                text = self._extract_text_from_pptx(file_content)
                if text and text.strip():
                    logger.info(f"[PPTX PROCESSING] ✅ {len(text)} chars extracted")
                    return text
                else:
                    logger.warning(f"[PPTX PROCESSING] ❌ Failed to extract text from PPTX")
                    return None
            
            elif file_lower.endswith(('.docx', '.doc')) or 'wordprocessingml' in content_type or 'msword' in content_type:
                logger.info(f"[DOCX PROCESSING] Extracting Word with python-docx...")
                text = self._extract_text_from_docx(file_content)
                if text and text.strip():
                    logger.info(f"[DOCX PROCESSING] ✅ {len(text)} chars extracted")
                    return text
                else:
                    logger.warning(f"[DOCX PROCESSING] ❌ Failed to extract text from DOCX")
                    return None
            
            elif file_lower.endswith(('.xlsx', '.xls')) or 'spreadsheetml' in content_type or 'ms-excel' in content_type:
                logger.info(f"[XLSX PROCESSING] Extracting Excel with openpyxl...")
                text = self._extract_text_from_xlsx(file_content)
                if text and text.strip():
                    logger.info(f"[XLSX PROCESSING] ✅ {len(text)} chars extracted")
                    return text
                else:
                    logger.warning(f"[XLSX PROCESSING] ❌ Failed to extract text from XLSX")
                    return None
            
            elif file_lower.endswith('.txt') or 'text/plain' in content_type:
                logger.info(f"[TXT PROCESSING] Decoding TXT...")
                decoded = file_content.decode('utf-8', errors='ignore')
                logger.info(f"[TXT PROCESSING] ✅ {len(decoded)} chars")
                return decoded
            
            else:
                # Unknown file type - try to detect and process accordingly
                logger.info(f"[UNKNOWN] Detecting file type from content...")
                
                # Try to detect by magic bytes
                if file_content.startswith(b'%PDF'):
                    logger.info(f"[UNKNOWN] Detected as PDF (magic bytes)")
                    return self._extract_text_from_pdf(file_content)
                
                elif file_content.startswith(b'PK\x03\x04'):  # ZIP magic bytes - PPTX/DOCX/XLSX all use ZIP
                    # Try to determine which type by examining the ZIP structure
                    try:
                        import zipfile
                        import io
                        
                        with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                            namelist = zf.namelist()
                            
                            # PPTX detection
                            if any('slide' in n.lower() for n in namelist):
                                logger.info(f"[UNKNOWN] Detected as PPTX (ZIP with slide files)")
                                return self._extract_text_from_pptx(file_content)
                            
                            # DOCX detection
                            elif 'word/document.xml' in namelist:
                                logger.info(f"[UNKNOWN] Detected as DOCX (ZIP with word/document.xml)")
                                return self._extract_text_from_docx(file_content)
                            
                            # XLSX detection
                            elif 'xl/workbook.xml' in namelist:
                                logger.info(f"[UNKNOWN] Detected as XLSX (ZIP with xl/workbook.xml)")
                                return self._extract_text_from_xlsx(file_content)
                    except Exception as e:
                        logger.warning(f"Could not determine ZIP type: {e}")
                
                # Try as text
                try:
                    decoded = file_content.decode('utf-8', errors='strict')
                    if decoded.strip():
                        logger.info(f"[UNKNOWN] ✅ Decoded as text: {len(decoded)} chars")
                        return decoded
                except UnicodeDecodeError:
                    pass
                
                logger.warning(f"[UNKNOWN] ❌ Cannot determine file type or extract text")
                return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[FILE DOWNLOAD] ❌ {type(e).__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"[FILE PROCESSING] ❌ {type(e).__name__}: {e}")
            return None
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Divide texto en chunks con overlap para mejor búsqueda.
        GARANTIZA: al menos 1 chunk, y si el contenido es muy largo, crea múltiples.
        
        Args:
            text: Texto a dividir
            chunk_size: Tamaño de cada chunk en caracteres
            overlap: Overlap entre chunks para contexto
        
        Returns:
            Lista de chunks (nunca vacía)
        """
        if not text or not text.strip():
            return [text] if text else [""]
        
        # Si el texto es pequeño, devolver como está
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():  # Solo agregar si no está vacío
                chunks.append(chunk)
            start = end - overlap  # Overlap para contexto
        
        # Garantizar que devolvemos al menos 1 chunk
        if not chunks:
            chunks = [text]
        
        return chunks
    
    def _chunk_text_semantic(self, text: str, max_chunk_size: int = 1500, similarity_threshold: float = 0.45) -> List[str]:
        """
        Divide texto en chunks basándose en LÍMITES TEMÁTICOS.
        
        Algoritmo:
        1. Dividir texto en segmentos (oraciones, bullets, párrafos)
        2. Calcular embedding de cada segmento
        3. Comparar similaridad coseno entre segmentos consecutivos
        4. Donde la similaridad baja del threshold → cortar (cambio de tema)
        5. Agrupar segmentos en chunks respetando max_chunk_size
        
        Args:
            text: Texto completo a dividir
            max_chunk_size: Tamaño máximo de cada chunk en caracteres
            similarity_threshold: Umbral de similaridad (menor = más chunks)
        
        Returns:
            Lista de chunks semánticamente coherentes
        """
        if not text or not text.strip():
            return [text] if text else [""]
        
        if len(text) <= max_chunk_size:
            return [text]
        
        # 1. Dividir en segmentos - manejar tanto oraciones como bullets/líneas de PPTX
        # Primero separar por dobles saltos de línea (párrafos/slides), luego por oraciones
        segments = []
        paragraphs = re.split(r'\n{2,}', text.strip())
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Si el párrafo es corto (< 300 chars), mantenerlo como un segmento
            if len(para) < 300:
                segments.append(para)
            else:
                # Dividir por oraciones o saltos de línea
                sub_segments = re.split(r'(?<=[.!?])\s+|\n', para)
                for seg in sub_segments:
                    seg = seg.strip()
                    if seg and len(seg) > 10:  # Solo segmentos con contenido real
                        segments.append(seg)
        
        # Filtrar segmentos vacíos o demasiado cortos
        segments = [s for s in segments if s and len(s.strip()) > 10]
        
        if len(segments) <= 1:
            logger.info("[SEMANTIC] Solo 1 segmento, fallback a sliding window")
            return self._chunk_text(text, chunk_size=1000, overlap=300)
        
        logger.info(f"[SEMANTIC] {len(segments)} segmentos detectados")
        
        # 2. Calcular embeddings de cada segmento
        try:
            sentence_embeddings = self.embedding_model.encode(segments)
        except Exception as e:
            logger.error(f"[SEMANTIC] Error encoding segments: {e}, fallback a sliding window")
            return self._chunk_text(text, chunk_size=1000, overlap=300)
        
        # 3. Calcular similaridad coseno entre segmentos consecutivos
        similarities = []
        for i in range(len(sentence_embeddings) - 1):
            a = sentence_embeddings[i]
            b = sentence_embeddings[i + 1]
            cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
            similarities.append(float(cos_sim))
        
        # 4. Detectar puntos de corte (donde la similaridad baja del threshold)
        breakpoints = []
        for i, sim in enumerate(similarities):
            if sim < similarity_threshold:
                breakpoints.append(i + 1)  # Cortar DESPUÉS del segmento i
        
        logger.info(f"[SEMANTIC] Similaridades: min={min(similarities):.3f}, max={max(similarities):.3f}, avg={sum(similarities)/len(similarities):.3f}")
        logger.info(f"[SEMANTIC] {len(breakpoints)} puntos de corte temático detectados (threshold={similarity_threshold})")
        
        # 5. Agrupar segmentos en chunks
        chunks = []
        current_chunk_parts = []
        current_length = 0
        
        for i, segment in enumerate(segments):
            # Si agregar este segmento excede el máximo, guardar chunk actual
            if current_length + len(segment) > max_chunk_size and current_chunk_parts:
                chunks.append('\n'.join(current_chunk_parts))
                current_chunk_parts = []
                current_length = 0
            
            current_chunk_parts.append(segment)
            current_length += len(segment) + 1
            
            # Si estamos en un punto de corte temático, guardar chunk
            if i in breakpoints and current_chunk_parts:
                chunks.append('\n'.join(current_chunk_parts))
                current_chunk_parts = []
                current_length = 0
        
        # No olvidar el último grupo
        if current_chunk_parts:
            chunks.append('\n'.join(current_chunk_parts))
        
        # Garantizar al menos 1 chunk
        if not chunks:
            chunks = [text]
        
        # Log de resultado
        sizes = [len(c) for c in chunks]
        logger.info(f"[SEMANTIC] Resultado: {len(chunks)} chunks, tamaños: {sizes}")
        
        return chunks
    
    def _calculate_chunk_importance(self, chunk: str, chunk_index: int, total_chunks: int, 
                                     full_text: str = None, document_title: str = None) -> float:
        """
        Calcula un score de importancia (0.0-1.0) para un chunk basado en:
        - Tipo de contenido (definición vs ejemplo)
        - Posición en el documento (inicio/conclusión vs medio)
        - Densidad de información
        - Presencia de palabras clave estructurales
        
        Args:
            chunk: El texto del chunk
            chunk_index: Índice del chunk (0-based)
            total_chunks: Total de chunks del documento
            full_text: Texto completo del documento (opcional, para contexto)
            document_title: Título del documento (opcional)
            
        Returns:
            Float entre 0.0 (ejemplo/detalle) y 1.0 (concepto central)
        """
        if not chunk or not chunk.strip():
            return 0.3  # Score bajo para chunks vacíos
        
        chunk_lower = chunk.lower()
        score = 0.5  # Score base
        
        # ===== 1. INDICADORES DE DEFINICIÓN/CONCEPTO CENTRAL (+) =====
        definition_patterns = [
            r'\b(es|son|se define como|significa|consiste en|se entiende por)\b',
            r'\b(definici[oó]n|concepto|principio|ley|teor[ií]a|fundamento)\b',
            r'\b(importante|esencial|fundamental|clave|b[aá]sico|principal)\b',
            r'\b(objetivo|prop[oó]sito|meta|fin|conclusi[oó]n)\b',
        ]
        for pattern in definition_patterns:
            if re.search(pattern, chunk_lower):
                score += 0.08
        
        # ===== 2. INDICADORES DE EJEMPLO/DETALLE (-) =====
        example_patterns = [
            r'\b(por ejemplo|ejemplo|e\.g\.|i\.e\.|como muestra|ilustra)\b',
            r'\b(caso particular|en este caso|supongamos|imagina)\b',
            r'\b(espec[ií]ficamente|particularmente|en concreto)\b',
            r'\b(ver figura|ver tabla|como se observa|seg[uú]n la imagen)\b',
        ]
        for pattern in example_patterns:
            if re.search(pattern, chunk_lower):
                score -= 0.05
        
        # ===== 3. POSICIÓN EN EL DOCUMENTO =====
        # Inicio y final suelen tener información más importante (intro/conclusión)
        if total_chunks > 1:
            position_ratio = chunk_index / (total_chunks - 1) if total_chunks > 1 else 0.5
            
            # Primer y último chunk son más importantes
            if chunk_index == 0:
                score += 0.12  # Introducción
            elif chunk_index == total_chunks - 1:
                score += 0.10  # Conclusión
            elif position_ratio < 0.25:
                score += 0.05  # Cerca del inicio
            elif position_ratio > 0.75:
                score += 0.03  # Cerca del final
            # El medio tiene score neutro
        
        # ===== 4. ESTRUCTURA/FORMATO =====
        # Títulos, bullets points, enumeraciones suelen ser importantes
        structure_patterns = [
            (r'^[A-Z][A-Z\s]+$', 0.15),  # TÍTULOS EN MAYÚSCULAS
            (r'^\d+[\.\)]\s', 0.08),  # Listas numeradas
            (r'^[-•]\s', 0.05),  # Bullet points
            (r'\b(paso \d|etapa \d|fase \d)\b', 0.06),  # Pasos de proceso
            (r'\b(primero|segundo|tercero|finalmente)\b', 0.04),  # Secuencias
        ]
        for pattern, bonus in structure_patterns:
            if re.search(pattern, chunk_lower, re.MULTILINE):
                score += bonus
        
        # ===== 5. DENSIDAD DE INFORMACIÓN =====
        # Chunks con más sustantivos/verbos técnicos vs relleno
        words = chunk_lower.split()
        if len(words) > 10:
            # Palabras funcionales (poco informativas)
            filler_words = {'el', 'la', 'los', 'las', 'de', 'del', 'al', 'a', 'en', 
                           'con', 'por', 'para', 'que', 'y', 'o', 'un', 'una', 'como',
                           'es', 'son', 'se', 'su', 'sus', 'este', 'esta', 'esto'}
            filler_count = sum(1 for w in words if w in filler_words)
            content_ratio = 1 - (filler_count / len(words))
            
            # Alta densidad de contenido = más importante
            if content_ratio > 0.7:
                score += 0.08
            elif content_ratio > 0.6:
                score += 0.04
        
        # ===== 6. LONGITUD DEL CHUNK =====
        # Chunks muy cortos suelen ser encabezados, muy largos pueden ser relleno
        chunk_len = len(chunk)
        if 200 < chunk_len < 1200:
            score += 0.05  # Longitud óptima
        elif chunk_len < 100:
            score -= 0.05  # Muy corto (quizás solo título)
        
        # ===== 7. TÍTULO DEL DOCUMENTO =====
        # Si el chunk contiene palabras del título, es más relevante
        if document_title:
            title_words = set(re.findall(r'\b[a-záéíóúñü]{4,}\b', document_title.lower()))
            chunk_words = set(re.findall(r'\b[a-záéíóúñü]{4,}\b', chunk_lower))
            overlap = len(title_words & chunk_words)
            if overlap > 0:
                score += min(0.10, overlap * 0.03)
        
        # Normalizar entre 0.1 y 1.0 (nunca 0 total)
        return max(0.1, min(1.0, score))
    
    def _calculate_importance_batch(self, chunks: List[str], document_title: str = None) -> List[float]:
        """
        Calcula importancia para múltiples chunks de forma eficiente.
        
        Args:
            chunks: Lista de chunks
            document_title: Título del documento
            
        Returns:
            Lista de scores de importancia (0.1-1.0)
        """
        if not chunks:
            return []
        
        # Concatenar full_text para contexto
        full_text = '\n'.join(chunks)
        total_chunks = len(chunks)
        
        scores = []
        for idx, chunk in enumerate(chunks):
            score = self._calculate_chunk_importance(
                chunk=chunk,
                chunk_index=idx,
                total_chunks=total_chunks,
                full_text=full_text,
                document_title=document_title
            )
            scores.append(score)
        
        # Log de distribución
        if scores:
            avg_score = sum(scores) / len(scores)
            logger.debug(f"[IMPORTANCE] {len(scores)} chunks scored, avg={avg_score:.3f}, "
                        f"min={min(scores):.3f}, max={max(scores):.3f}")
        
        return scores

    def analyze_module(self, module, user_token: str) -> bool:
        """
        Analiza todos los items de un módulo y crea embeddings.
        Limpia embeddings viejos y crea nuevos con contenido actualizado.
        
        Args:
            module: El objeto Module a analizar
            user_token: Token de Canvas para descargar archivos
            
        Returns:
            True si el análisis fue exitoso
        """
        debug_service = get_debug_service()
        try:
            collection_name = f"module_{module.id}_course_{module.course.id}"
            debug_service.log_rag_analysis_start(module.id, module.name)
            logger.info(f"Starting module analysis: {collection_name}")
            
            if self.using_chromadb and self.client:
                # Usar ChromaDB - limpiar colección vieja si existe
                try:
                    self.client.delete_collection(name=collection_name)
                    logger.info(f"Deleted old collection {collection_name}")
                except:
                    pass  # Collection doesn't exist yet
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            else:
                # Usar en memoria - limpiar y crear nueva
                if collection_name in self.in_memory_db:
                    logger.info(f"Clearing old in-memory collection {collection_name}")
                    del self.in_memory_db[collection_name]
                
                # Crear nueva colección vacía
                self.in_memory_db[collection_name] = {
                    'documents': [],
                    'embeddings': [],
                    'metadatas': [],
                    'importance_scores': []  # NUEVO: Scores jerárquicos de importancia
                }
                collection = self.in_memory_db[collection_name]
            
            # Procesar cada item del módulo
            items = module.items.all()
            embeddings_count = 0
            analyzed_documents = []  # Para registrar en debug
            
            for i, item in enumerate(items):
                try:
                    logger.info(f"[ITEM {i+1}/{len(items)}] Processing: {item.title}")
                    
                    # Obtener texto del item
                    text = f"{item.title} - {item.get_item_type_display()}"
                    extracted = None
                    is_external_content = False
                    
                    if item.url:
                        logger.info(f"  [EXTRACT] File URL: {item.url[:80]}...")
                        extracted = self._extract_text_from_file(item.url, user_token)
                        
                        # Log detallado del resultado de extracción
                        if extracted:
                            logger.info(f"  [EXTRACT] ✅ Got {len(extracted)} chars")
                            text = f"{text}\n\n{extracted}"
                            is_external_content = True
                        else:
                            logger.warning(f"  [EXTRACT] ❌ Failed to extract content (returned None)")
                            logger.warning(f"  [EXTRACT] Will use only title: '{text}' ({len(text)} chars)")
                            # IMPORTANTE: Si no se extrae, seguir adelante con solo el título
                            is_external_content = False
                    
                    # Validar que el documento no sea binario corrupto
                    if is_external_content and text.startswith('%PDF'):
                        logger.error(f"  [VALIDATE] ❌ Document contains raw PDF binary - skipping!")
                        continue
                    
                    # Si el contenido tiene texto extraído, dividir en chunks SEMÁNTICOS
                    # Cada chunk agrupa oraciones del mismo tema
                    if extracted:
                        # Usar chunking semántico: detecta límites temáticos
                        raw_chunks = self._chunk_text_semantic(text, max_chunk_size=1500, similarity_threshold=0.45)
                        
                        # Limpiar y filtrar chunks: eliminar ruido residual
                        chunks = []
                        for rc in raw_chunks:
                            cleaned = self._clean_slide_text(rc)
                            # Solo mantener chunks con contenido significativo (> 30 chars)
                            if cleaned and len(cleaned.strip()) > 30:
                                chunks.append(cleaned)
                            else:
                                logger.debug(f"  [FILTER] Descartando chunk basura: '{rc[:80]}...'")
                        
                        if not chunks:
                            logger.warning(f"  [FILTER] Todos los chunks descartados por ruido, usando título")
                            chunks = [text.split('\n')[0]]  # Usar solo título
                        
                        logger.info(f"  [CHUNKS] {len(text)} chars -> {len(raw_chunks)} raw -> {len(chunks)} clean chunks")
                        
                        # NUEVO: Calcular importancia de cada chunk
                        importance_scores = self._calculate_importance_batch(chunks, document_title=item.title)
                        
                        # Crear embedding para cada chunk
                        for chunk_idx, chunk in enumerate(chunks):
                            embedding = self.embedding_model.encode(chunk).tolist()
                            importance = importance_scores[chunk_idx] if chunk_idx < len(importance_scores) else 0.5
                            embeddings_count += 1
                            
                            doc_id = f"item_{item.id}_chunk_{chunk_idx}"
                            metadata = {
                                'item_id': str(item.id),
                                'item_title': item.title,
                                'item_type': item.get_item_type_display(),
                                'module_id': str(module.id),
                                'chunk_index': str(chunk_idx),
                                'chunk_total': str(len(chunks)),
                                'has_content': 'yes' if is_external_content else 'no',
                                'importance_score': str(round(importance, 3)),  # NUEVO
                            }
                            
                            if self.using_chromadb and self.client:
                                collection.add(
                                    ids=[doc_id],
                                    embeddings=[embedding],
                                    documents=[chunk],
                                    metadatas=[metadata]
                                )
                            else:
                                # En memoria
                                collection['documents'].append(chunk)
                                collection['embeddings'].append(embedding)
                                collection['metadatas'].append(metadata)
                                collection['importance_scores'].append(importance)  # NUEVO
                        
                        logger.debug(f"  [DONE] Created {len(chunks)} embeddings with importance scores")
                        
                        # Crear embeddings SEPARADOS para tablas (si el archivo era PPTX)
                        pptx_tables = getattr(self, '_last_pptx_tables', [])
                        if pptx_tables:
                            logger.info(f"  [TABLES] Creating {len(pptx_tables)} separate table embeddings")
                            for tbl_idx, tbl in enumerate(pptx_tables):
                                # Texto enriquecido: título del slide + tabla en Markdown
                                table_text = f"{item.title} - Tabla en: {tbl['slide_title']}\n\n{tbl['markdown']}"
                                table_text_clean = self._clean_slide_text(table_text)
                                
                                if not table_text_clean or len(table_text_clean.strip()) < 20:
                                    continue
                                
                                tbl_embedding = self.embedding_model.encode(table_text_clean).tolist()
                                tbl_importance = 0.75  # Alta importancia para datos estructurados
                                embeddings_count += 1
                                
                                tbl_doc_id = f"item_{item.id}_table_{tbl_idx}"
                                tbl_metadata = {
                                    'item_id': str(item.id),
                                    'item_title': item.title,
                                    'item_type': item.get_item_type_display(),
                                    'module_id': str(module.id),
                                    'content_type': 'table',
                                    'table_slide': str(tbl['slide_num']),
                                    'table_slide_title': tbl['slide_title'],
                                    'table_rows': str(tbl['row_count']),
                                    'has_content': 'yes',
                                    'importance_score': str(tbl_importance),
                                }
                                
                                if self.using_chromadb and self.client:
                                    collection.add(
                                        ids=[tbl_doc_id],
                                        embeddings=[tbl_embedding],
                                        documents=[table_text_clean],
                                        metadatas=[tbl_metadata]
                                    )
                                else:
                                    collection['documents'].append(table_text_clean)
                                    collection['embeddings'].append(tbl_embedding)
                                    collection['metadatas'].append(tbl_metadata)
                                    collection['importance_scores'].append(tbl_importance)
                                
                                logger.debug(f"    [TABLE EMB] #{tbl_idx}: slide {tbl['slide_num']}, {tbl['row_count']} rows")
                            
                            # Limpiar tablas almacenadas
                            self._last_pptx_tables = []
                    else:
                        # Sin contenido extraído - usar solo título como documento
                        embedding = self.embedding_model.encode(text).tolist()
                        importance = 0.3  # Score bajo para solo títulos
                        embeddings_count += 1
                        
                        doc_id = f"item_{item.id}"
                        metadata = {
                            'item_id': str(item.id),
                            'item_title': item.title,
                            'item_type': item.get_item_type_display(),
                            'module_id': str(module.id),
                            'has_content': 'no',
                            'importance_score': str(round(importance, 3)),  # NUEVO
                        }
                        
                        if self.using_chromadb and self.client:
                            collection.add(
                                ids=[doc_id],
                                embeddings=[embedding],
                                documents=[text],
                                metadatas=[metadata]
                            )
                        else:
                            # En memoria
                            collection['documents'].append(text)
                            collection['embeddings'].append(embedding)
                            collection['metadatas'].append(metadata)
                            collection['importance_scores'].append(importance)  # NUEVO
                        
                        logger.debug(f"  [DONE] Created 1 embedding (sin contenido extraído, importance={importance})")

                    
                    # Log del embedding
                    debug_service.log_embedding_created(item.id, item.title, len(embedding))
                    
                except Exception as e:
                    logger.error(f"Error processing item {item.id}: {e}")
                    debug_service.log_error("EMBEDDING", f"Error procesando item {item.id}", e)
                    continue
            
            # Registrar documentos analizados
            debug_service.log_analyzed_documents(module.id, module.name, analyzed_documents)
            
            # Actualizar stats de memoria
            if not self.using_chromadb:
                # Guardar embeddings en JSON para persistencia
                self._save_json_embeddings(collection_name, collection)
                debug_service.log_memory_db_update(
                    collection_name,
                    len(collection['documents']),
                    len(collection['embeddings'])
                )
            
            # Log de finalización
            debug_service.log_rag_analysis_complete(module.id, len(items), embeddings_count)
            logger.info(f"Module analysis completed: {len(items)} items processed, {embeddings_count} embeddings")
            
            if embeddings_count == 0:
                logger.error(f"[ANALYZE] ❌ 0 embeddings created for module {module.id} - analysis failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing module: {e}")
            debug_service.log_error("RAG_ANALYSIS", f"Error en analyze_module para módulo {module.id}", e)
            return False
    
    def search_context(self, query: str, module_id: int, course_id: int, 
                      top_k: int = 5, query_type: str = 'general',
                      importance_weight: float = None) -> List[dict]:
        """
        Busca contexto relevante en la base de conocimiento.
        
        NUEVO: Usa ranking combinado de similitud + importancia jerárquica.
        
        Args:
            query: Pregunta del estudiante
            module_id: ID del módulo a buscar
            course_id: ID del curso
            top_k: Número de resultados a retornar
            query_type: Tipo de pregunta ('summary', 'definition', 'comparison', etc.)
            importance_weight: Peso de importancia (0-1). Si None, se calcula según query_type.
        
        Returns:
            Lista de documentos relevantes con metadata
        """
        # Definir pesos de importancia por tipo de consulta
        # Para resúmenes: importancia alta (priorizar conceptos centrales)
        # Para preguntas específicas: importancia baja (priorizar similitud)
        IMPORTANCE_WEIGHTS = {
            'summary': 0.4,        # Priorizar chunks conceptuales importantes
            'definition': 0.2,     # Balance hacia similitud semántica
            'comparison': 0.25,    # Balance moderado
            'list': 0.3,           # Priorizar estructura
            'specific': 0.1,       # Casi solo similitud
            'explanation': 0.2,    # Balance hacia similitud
            'general': 0.15,       # Default: priorizar similitud con peso leve
        }
        
        if importance_weight is None:
            importance_weight = IMPORTANCE_WEIGHTS.get(query_type, 0.15)
        
        debug_service = get_debug_service()
        try:
            collection_name = f"module_{module_id}_course_{course_id}"
            
            if self.using_chromadb and self.client:
                # Usar ChromaDB
                try:
                    collection = self.client.get_collection(collection_name)
                    total_docs = collection.count()
                    # Fetch more candidates for reranking with importance
                    fetch_k = min(total_docs, max(top_k * 3, 15))
                    logger.info(f"[RAG] Collection {collection_name}: {total_docs} docs, fetching {fetch_k} for reranking, final top_k={top_k}")
                    
                    results = collection.query(
                        query_texts=[query],
                        n_results=fetch_k,
                        include=["documents", "metadatas", "distances"]
                    )
                    
                    candidates = []
                    if results['documents'] and results['documents'][0]:
                        for doc, metadata, distance in zip(
                            results['documents'][0],
                            results['metadatas'][0],
                            results['distances'][0]
                        ):
                            # ChromaDB cosine distance: 0 = idéntico, 2 = opuesto
                            similarity = max(0, 1 - (distance / 2))
                            
                            # Recuperar importance_score de metadata
                            try:
                                importance = float(metadata.get('importance_score', 0.5))
                            except (ValueError, TypeError):
                                importance = 0.5
                            
                            # Score combinado: (1-w)*similarity + w*importance
                            combined = (1 - importance_weight) * similarity + importance_weight * importance
                            
                            candidates.append({
                                'content': doc,
                                'metadata': metadata,
                                'relevance_score': similarity,
                                'importance_score': importance,
                                'combined_score': combined
                            })
                    
                    # Reranking por score combinado
                    candidates.sort(key=lambda x: x['combined_score'], reverse=True)
                    context_list = candidates[:top_k]
                    
                    # Add ranking metadata
                    for i, item in enumerate(context_list):
                        item['metadata'] = item['metadata'].copy()
                        item['metadata']['importance_used'] = str(round(item['importance_score'], 3))
                        item['metadata']['combined_score'] = str(round(item['combined_score'], 3))
                    
                    logger.info(f"[RAG] Retrieved {len(context_list)} chunks after reranking (importance_weight={importance_weight})")
                    debug_service.log_rag_search(query, module_id, len(context_list))
                    return context_list
                except Exception as e:
                    logger.warning(f"ChromaDB collection not found: {e}")
                    debug_service.log_error("SEARCH", f"ChromaDB collection not found: {collection_name}", e)
                    return []
            else:
                # Usar en memoria
                if collection_name not in self.in_memory_db:
                    logger.warning(f"Collection {collection_name} not found in memory")
                    debug_service.log_error("SEARCH", f"Colección no encontrada: {collection_name}", None)
                    return []
                
                collection = self.in_memory_db[collection_name]
                
                if not collection['documents']:
                    return []
                
                # Calcular similitud con embedding
                try:
                    query_embedding = self.embedding_model.encode(query)
                    
                    # Intentar usar sklearn, si no está disponible usar numpy
                    try:
                        from sklearn.metrics.pairwise import cosine_similarity
                        similarities = [
                            cosine_similarity([query_embedding], [emb])[0][0]
                            for emb in collection['embeddings']
                        ]
                    except ImportError:
                        # Implementar similitud coseno manual con numpy
                        import numpy as np
                        query_norm = np.linalg.norm(query_embedding)
                        similarities = []
                        for emb in collection['embeddings']:
                            emb_norm = np.linalg.norm(emb)
                            similarity = np.dot(query_embedding, emb) / (query_norm * emb_norm + 1e-8)
                            similarities.append(float(similarity))
                    
                    # NUEVO: Obtener importance_scores (compatible con colecciones antiguas)
                    importance_scores = collection.get('importance_scores', [])
                    has_importance = len(importance_scores) == len(similarities)
                    
                    # NUEVO: Calcular scores combinados
                    # final_score = (1 - weight) * similarity + weight * importance
                    combined_scores = []
                    for i, sim in enumerate(similarities):
                        if has_importance:
                            imp = importance_scores[i]
                        else:
                            # Fallback: obtener de metadata si existe
                            try:
                                imp = float(collection['metadatas'][i].get('importance_score', 0.5))
                            except (ValueError, KeyError):
                                imp = 0.5
                        
                        # Score combinado ponderado
                        combined = (1 - importance_weight) * sim + importance_weight * imp
                        combined_scores.append({
                            'index': i,
                            'similarity': sim,
                            'importance': imp,
                            'combined_score': combined
                        })
                    
                    # Ordenar por score combinado
                    combined_scores.sort(key=lambda x: x['combined_score'], reverse=True)
                    top_entries = combined_scores[:top_k]
                    
                    context_list = []
                    for entry in top_entries:
                        idx = entry['index']
                        doc = collection['documents'][idx]
                        metadata = collection['metadatas'][idx].copy()
                        metadata['importance_used'] = str(round(entry['importance'], 3))
                        metadata['combined_score'] = str(round(entry['combined_score'], 3))
                        metadata['chunk_length'] = str(len(doc))
                        
                        # Incluir TODOS los chunks seleccionados sin filtrar por longitud
                        # DeepSeek puede manejar chunks cortos y decidir su relevancia
                        context_list.append({
                            'content': doc,
                            'metadata': metadata,
                            'relevance_score': float(entry['similarity']),
                            'importance_score': float(entry['importance']),
                            'combined_score': float(entry['combined_score'])
                        })
                    
                    # Log del ranking
                    if has_importance and importance_weight > 0:
                        logger.debug(f"[SEARCH] query_type={query_type}, importance_weight={importance_weight}, "
                                    f"reranked {len(context_list)} results")
                    
                    debug_service.log_rag_search(query, module_id, len(context_list))
                    return context_list
                except Exception as e:
                    logger.error(f"Error computing similarity: {e}")
                    debug_service.log_error("SIMILARITY", "Error calculando similitud", e)
                    return []
            
        except Exception as e:
            logger.error(f"Error searching context: {e}")
            debug_service.log_error("SEARCH", "Error en search_context", e)
            return []
    
    def delete_collection(self, module_id: int, course_id: int):
        """
        Elimina la colección de un módulo (cuando se actualiza, etc.)
        """
        try:
            collection_name = f"module_{module_id}_course_{course_id}"
            
            if self.using_chromadb and self.client:
                try:
                    self.client.delete_collection(collection_name)
                    logger.info(f"Deleted ChromaDB collection: {collection_name}")
                except Exception as e:
                    logger.error(f"Error deleting ChromaDB collection: {e}")
            
            # Eliminar de en-memoria si existe
            if collection_name in self.in_memory_db:
                del self.in_memory_db[collection_name]
                logger.info(f"Deleted in-memory collection: {collection_name}")
                
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
    
    def check_collection_exists(self, collection_name: str) -> bool:
        """
        Verifica si una colección existe (tiene embeddings).
        Útil para saber si un módulo ya fue analizado.
        
        Args:
            collection_name: Nombre de la colección (ej: "module_2_course_1")
            
        Returns:
            True si la colección existe y tiene documentos, False de otro modo
        """
        try:
            # Verificar en ChromaDB
            if self.using_chromadb and self.client:
                try:
                    collection = self.client.get_collection(collection_name)
                    count = collection.count()
                    return count > 0
                except Exception as e:
                    logger.debug(f"Collection not found in ChromaDB: {collection_name}")
            
            # Verificar en memoria
            if collection_name in self.in_memory_db:
                docs = self.in_memory_db[collection_name].get('documents', [])
                return len(docs) > 0
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False
    
    def get_embeddings_count(self, collection_name: str) -> int:
        """
        Obtiene el conteo de embeddings en una colección.
        
        Args:
            collection_name: Nombre de la colección
            
        Returns:
            Número de embeddings en la colección, 0 si no existe
        """
        try:
            # Verificar en ChromaDB
            if self.using_chromadb and self.client:
                try:
                    collection = self.client.get_collection(collection_name)
                    count = collection.count()
                    return count
                except Exception as e:
                    logger.debug(f"Collection not found in ChromaDB: {collection_name}")
            
            # Verificar en memoria
            if collection_name in self.in_memory_db:
                docs = self.in_memory_db[collection_name].get('documents', [])
                return len(docs)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error getting embeddings count: {e}")
            return 0


# Instancia global (singleton)
rag_service = None


def get_rag_service() -> RAGService:
    """Obtiene la instancia global del servicio RAG."""
    global rag_service
    if rag_service is None:
        rag_service = RAGService()
    return rag_service
