# tu_app/rag_service.py

import os
import json
import logging
import warnings
import time
import pickle
from pathlib import Path
from typing import List, Optional
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
    
    def _extract_text_from_pptx(self, pptx_bytes) -> Optional[str]:
        """
        Extrae texto de un archivo PPTX (PowerPoint).
        Extrae texto de todos los slides.
        """
        if not PPTX_AVAILABLE:
            logger.warning("python-pptx not available, returning None for PPTX file")
            return None
        
        try:
            import io
            logger.info(f"Attempting to extract PPTX with python-pptx, file size: {len(pptx_bytes)} bytes")
            
            presentation = Presentation(io.BytesIO(pptx_bytes))
            logger.info(f"PPTX opened successfully, total slides: {len(presentation.slides)}")
            
            text = ""
            for slide_num, slide in enumerate(presentation.slides):
                slide_text = ""
                
                # Extraer texto de todas las formas (shapes) en el slide
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        shape_text = shape.text.strip()
                        if shape_text:
                            slide_text += shape_text + " "
                    
                    # Si es una tabla, extraer su contenido
                    if shape.shape_type == 14:  # 14 = MSO_SHAPE_TYPE.TABLE
                        try:
                            table = shape.table
                            for row in table.rows:
                                for cell in row.cells:
                                    if cell.text.strip():
                                        slide_text += cell.text.strip() + " "
                        except Exception as e:
                            logger.warning(f"Could not extract table from slide {slide_num + 1}: {e}")
                
                if slide_text:
                    logger.info(f"Slide {slide_num + 1}: extracted {len(slide_text)} chars")
                    text += f"\n--- Slide {slide_num + 1} ---\n{slide_text}"
                else:
                    logger.info(f"Slide {slide_num + 1}: no text found")
            
            final_text = text if text.strip() else "[PPTX vacío o sin contenido de texto]"
            logger.info(f"PPTX extraction complete: total {len(final_text)} chars extracted")
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
        """
        Crea o obtiene una colección en ChromaDB.
        Una colección por módulo para mejorar queries.
        """
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            return collection
        except Exception as e:
            logger.error(f"Error creating/getting collection {collection_name}: {e}")
            raise
    
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
    
    def _chunk_text_semantic(self, text: str, similarity_threshold: float = 0.5, min_chunk_size: int = 100) -> List[str]:
        """
        Divide texto en chunks basado en cambios temáticos (SEMANTIC).
        Detecta límites naturales cuando la similaridad entre oraciones cae.
        
        Args:
            text: Texto a dividir
            similarity_threshold: Si similaridad < threshold → nuevo chunk (0.0-1.0)
            min_chunk_size: Tamaño mínimo de chunk en caracteres
        
        Returns:
            Lista de chunks semánticos
        """
        if not text or not text.strip():
            return [text] if text else [""]
        
        # Si el texto es pequeño, devolver completo
        if len(text) < min_chunk_size * 2:
            return [text]
        
        import re
        import numpy as np
        
        # Dividir en oraciones (regex simple pero efectivo)
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            return [text]
        
        try:
            # Calcular embeddings para cada oración (BATCH = rápido)
            logger.info(f"[SEMANTIC] Computing embeddings for {len(sentences)} sentences...")
            embeddings = self.embedding_model.encode(sentences, show_progress_bar=False)
            embeddings = np.array(embeddings)
            
            # Calcular similaridad coseno entre oraciones consecutivas
            chunks = []
            current_chunk = sentences[0]
            
            for i in range(1, len(sentences)):
                # Similaridad coseno: dot(a,b) / (norm(a) * norm(b))
                dot_product = np.dot(embeddings[i-1], embeddings[i])
                norm_product = np.linalg.norm(embeddings[i-1]) * np.linalg.norm(embeddings[i])
                similarity = dot_product / norm_product if norm_product > 0 else 0
                
                # Si similaridad BAJA → tema diferente → nuevo chunk
                if similarity < similarity_threshold and len(current_chunk) >= min_chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = sentences[i]
                    logger.debug(f"  [SEMANTIC] New chunk (sim={similarity:.3f}): {sentences[i][:50]}...")
                else:
                    # Continuar acumulando en el mismo chunk
                    current_chunk += " " + sentences[i]
            
            # Agregar último chunk
            if current_chunk:
                chunks.append(current_chunk)
            
            # Garantizar chunks válidos
            if not chunks:
                chunks = [text]
            
            logger.info(f"[SEMANTIC] ✅ {len(sentences)} sentences → {len(chunks)} semantic chunks")
            return chunks
            
        except Exception as e:
            logger.warning(f"[SEMANTIC] Error: {e}. Fallback a sliding window.")
            # Fallback al método original si hay error
            return self._chunk_text(text, chunk_size=1000, overlap=200)
    
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
                collection = self.client.get_or_create_collection(name=collection_name)
            else:
                # Usar en memoria - limpiar y crear nueva
                if collection_name in self.in_memory_db:
                    logger.info(f"Clearing old in-memory collection {collection_name}")
                    del self.in_memory_db[collection_name]
                
                # Crear nueva colección vacía
                self.in_memory_db[collection_name] = {
                    'documents': [],
                    'embeddings': [],
                    'metadatas': []
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
                    
                    # Si el contenido tiene texto extraído, usar SEMANTIC CHUNKING
                    # Esto divide por cambios temáticos, no solo tamaño
                    if extracted:
                        # ✨ SEMANTIC: Divide detectando cambios de tema
                        chunks = self._chunk_text_semantic(
                            text,
                            similarity_threshold=0.45,
                            min_chunk_size=150
                        )
                        
                        logger.info(f"  [SEMANTIC] {len(text)} chars → {len(chunks)} semantic chunks")
                        
                        # Crear embedding para cada chunk
                        for chunk_idx, chunk in enumerate(chunks):
                            embedding = self.embedding_model.encode(chunk).tolist()
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
                        
                        logger.debug(f"  [DONE] Created {len(chunks)} embeddings")
                    else:
                        # Sin contenido extraído - usar solo título como documento
                        embedding = self.embedding_model.encode(text).tolist()
                        embeddings_count += 1
                        
                        doc_id = f"item_{item.id}"
                        metadata = {
                            'item_id': str(item.id),
                            'item_title': item.title,
                            'item_type': item.get_item_type_display(),
                            'module_id': str(module.id),
                            'has_content': 'no',
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
                        
                        logger.debug(f"  [DONE] Created 1 embedding (sin contenido extraído)")

                    
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
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing module: {e}")
            debug_service.log_error("RAG_ANALYSIS", f"Error en analyze_module para módulo {module.id}", e)
            return False
    
    def search_context(self, query: str, module_id: int, course_id: int, 
                      top_k: int = 5) -> List[dict]:
        """
        Busca contexto relevante en la base de conocimiento.
        
        Args:
            query: Pregunta del estudiante
            module_id: ID del módulo a buscar
            course_id: ID del curso
            top_k: Número de resultados a retornar
        
        Returns:
            Lista de documentos relevantes con metadata
        """
        debug_service = get_debug_service()
        try:
            collection_name = f"module_{module_id}_course_{course_id}"
            
            if self.using_chromadb and self.client:
                # Usar ChromaDB
                try:
                    collection = self.client.get_collection(collection_name)
                    
                    results = collection.query(
                        query_texts=[query],
                        n_results=top_k,
                        include=["documents", "metadatas", "distances"]
                    )
                    
                    context_list = []
                    if results['documents'] and results['documents'][0]:
                        for doc, metadata, distance in zip(
                            results['documents'][0],
                            results['metadatas'][0],
                            results['distances'][0]
                        ):
                            context_list.append({
                                'content': doc,
                                'metadata': metadata,
                                'relevance_score': 1 - distance
                            })
                    
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
                    
                    # Obtener top_k más similares
                    top_indices = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)[:top_k]
                    
                    context_list = []
                    for idx in top_indices:
                        doc = collection['documents'][idx]
                        # Filtrar documentos muy cortos (probablemente solo nombres de archivo)
                        # Aceptar si tiene > 100 caracteres O si contiene contenido real
                        if len(doc) > 100:
                            context_list.append({
                                'content': doc,
                                'metadata': collection['metadatas'][idx],
                                'relevance_score': float(similarities[idx])
                            })
                    
                    # Si no hay documentos largos, devolver los que haya (fallback)
                    if not context_list:
                        for idx in top_indices:
                            context_list.append({
                                'content': collection['documents'][idx],
                                'metadata': collection['metadatas'][idx],
                                'relevance_score': float(similarities[idx])
                            })
                    
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
