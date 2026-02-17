# tu_app/rag_service.py

import os
import json
import logging
import warnings
import time
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
        
        # Modelo de embeddings
        self.embedding_model = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2'
        )
        
        # En memoria: almacenar documentos por módulo
        self.in_memory_db = {}
        
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
        
        logger.info(f"RAG Service initialized - Using ChromaDB: {self.using_chromadb}")
    
    def create_or_get_collection(self, collection_name: str):
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
        Descarga y extrae texto de arquivos de Canvas.
        Soporta: PDF, TXT, DOCX, etc.
        """
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(file_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Por ahora retornamos como texto
            # En producción, usar libraries de parsing (pdfplumber, python-docx, etc.)
            if file_url.endswith('.txt'):
                return response.text
            elif file_url.endswith('.pdf'):
                logger.warning(f"PDF processing not fully implemented yet: {file_url}")
                return f"[PDF Document: {file_url}]"
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_url}: {e}")
            return None
    
    def analyze_module(self, module, user_token: str) -> bool:
        """
        Analiza todos los items de un módulo y crea embeddings.
        
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
                # Usar ChromaDB
                collection = self.client.get_or_create_collection(name=collection_name)
            else:
                # Usar en memoria
                if collection_name not in self.in_memory_db:
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
                    # Obtener texto del item
                    text = f"{item.title} - {item.get_item_type_display()}"
                    
                    if item.url:
                        extracted = self._extract_text_from_file(item.url, user_token)
                        if extracted:
                            text = f"{text}\n\n{extracted}"
                    
                    # Generar embedding
                    embedding = self.embedding_model.encode(text).tolist()
                    embeddings_count += 1
                    
                    # Almacenar documento para logging
                    analyzed_documents.append({
                        'item_id': item.id,
                        'title': item.title,
                        'item_type': item.get_item_type_display(),
                        'content': text[:300],  # Primeros 300 caracteres
                    })
                    
                    # Almacenar
                    doc_id = f"item_{item.id}"
                    metadata = {
                        'item_id': str(item.id),
                        'item_title': item.title,
                        'item_type': item.get_item_type_display(),
                        'module_id': str(module.id),
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
                    
                    # Log del embedding
                    debug_service.log_embedding_created(item.id, item.title, len(embedding))
                    logger.debug(f"Processed item {i+1}/{len(items)}: {item.title}")
                    
                except Exception as e:
                    logger.error(f"Error processing item {item.id}: {e}")
                    debug_service.log_error("EMBEDDING", f"Error procesando item {item.id}", e)
                    continue
            
            # Registrar documentos analizados
            debug_service.log_analyzed_documents(module.id, module.name, analyzed_documents)
            
            # Actualizar stats de memoria
            if not self.using_chromadb:
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
                      top_k: int = 3) -> List[dict]:
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


# Instancia global (singleton)
rag_service = None


def get_rag_service() -> RAGService:
    """Obtiene la instancia global del servicio RAG."""
    global rag_service
    if rag_service is None:
        rag_service = RAGService()
    return rag_service
