"""
Servicio de Debugging y Monitoring para Kairos AI Tutoring System
Permite a los desarrolladores ver qué está sucediendo adentro del sistema
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class DebugEvent:
    """Registro individual de un evento del sistema"""
    def __init__(self, event_type: str, message: str, data: Dict[str, Any] = None):
        self.timestamp = datetime.now()
        self.event_type = event_type  # "RAG", "DEEPSEEK", "EMBEDDING", "ERROR"
        self.message = message
        self.data = data or {}
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'type': self.event_type,
            'message': self.message,
            'data': self.data
        }


class DebugService:
    """Servicio centralizado para debugging y observabilidad"""
    
    def __init__(self, max_events: int = 1000):
        self.events: List[DebugEvent] = []
        self.max_events = max_events
        self.rag_stats = {
            'modules_analyzed': 0,
            'total_embeddings': 0,
            'collections_created': 0,
            'last_analysis': None,
        }
        self.deepseek_stats = {
            'total_calls': 0,
            'total_tokens': 0,
            'avg_response_time': 0,
            'last_call': None,
        }
        self.memory_db_stats = {
            'collections': {},  # {collection_name: {'docs': count, 'embeddings': count}}
        }
        self.analyzed_documents = {}  # {module_id: [{'title': str, 'type': str, 'content': str, ...}]}
    
    def log_event(self, event_type: str, message: str, data: Dict[str, Any] = None):
        """Registra un evento del sistema"""
        event = DebugEvent(event_type, message, data)
        self.events.append(event)
        
        # Mantener bajo el límite de eventos
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # También registrar en logs estándar
        logger.info(f"[{event_type}] {message} | Data: {json.dumps(data or {}, default=str, ensure_ascii=False)}")
    
    def log_rag_analysis_start(self, module_id: int, module_name: str):
        """Log cuando inicia análisis de un módulo"""
        self.log_event(
            'RAG',
            f'🔍 Iniciando análisis de módulo: {module_name}',
            {'module_id': module_id, 'module_name': module_name, 'action': 'start'}
        )
    
    def log_rag_analysis_complete(self, module_id: int, items_count: int, embeddings_generated: int):
        """Log cuando termina análisis"""
        self.rag_stats['modules_analyzed'] += 1
        self.rag_stats['total_embeddings'] += embeddings_generated
        self.rag_stats['last_analysis'] = datetime.now().isoformat()
        
        self.log_event(
            'RAG',
            f'✅ Análisis completado - {items_count} items, {embeddings_generated} embeddings',
            {
                'module_id': module_id,
                'items': items_count,
                'embeddings': embeddings_generated,
                'action': 'complete'
            }
        )
    
    def log_embedding_created(self, item_id: int, item_title: str, embedding_dim: int):
        """Log de créación de embedding individual"""
        self.log_event(
            'EMBEDDING',
            f'📊 Embedding creado: {item_title} (dim: {embedding_dim})',
            {
                'item_id': item_id,
                'title': item_title,
                'dimensions': embedding_dim
            }
        )
    
    def log_deepseek_call(self, prompt: str, response: str, tokens_used: int, response_time_ms: float):
        """Log de llamada a DeepSeek"""
        self.deepseek_stats['total_calls'] += 1
        self.deepseek_stats['total_tokens'] += tokens_used
        self.deepseek_stats['last_call'] = datetime.now().isoformat()
        
        # Calcular promedio de tiempo
        if self.deepseek_stats['total_calls'] > 1:
            self.deepseek_stats['avg_response_time'] = (
                self.deepseek_stats['avg_response_time'] * (self.deepseek_stats['total_calls'] - 1) +
                response_time_ms
            ) / self.deepseek_stats['total_calls']
        else:
            self.deepseek_stats['avg_response_time'] = response_time_ms
        
        # Truncar prompt/response para logs si son muy largos
        prompt_preview = prompt[:100] + '...' if len(prompt) > 100 else prompt
        response_preview = response[:150] + '...' if len(response) > 150 else response
        
        self.log_event(
            'DEEPSEEK',
            f'🤖 Respuesta de DeepSeek ({response_time_ms:.2f}ms)',
            {
                'prompt': prompt_preview,
                'response': response_preview,
                'tokens': tokens_used,
                'response_time_ms': response_time_ms,
                'total_calls': self.deepseek_stats['total_calls']
            }
        )
    
    def log_rag_search(self, query: str, module_id: int, results_count: int):
        """Log de búsqueda en RAG"""
        self.log_event(
            'RAG',
            f'🔎 Búsqueda RAG: "{query}" → {results_count} resultados',
            {
                'query': query,
                'module_id': module_id,
                'results': results_count
            }
        )
    
    def log_memory_db_update(self, collection_name: str, doc_count: int, embedding_count: int):
        """Log de actualización de base de datos en memoria"""
        self.memory_db_stats['collections'][collection_name] = {
            'docs': doc_count,
            'embeddings': embedding_count,
            'updated': datetime.now().isoformat()
        }
        
        self.log_event(
            'MEMORY_DB',
            f'💾 Colección actualizada: {collection_name}',
            {
                'collection': collection_name,
                'documents': doc_count,
                'embeddings': embedding_count
            }
        )
    
    def log_error(self, error_type: str, message: str, exception: Exception = None):
        """Log de errores"""
        exc_info = str(exception) if exception else ''
        self.log_event(
            'ERROR',
            f'❌ {error_type}: {message}',
            {
                'type': error_type,
                'message': message,
                'exception': exc_info
            }
        )
    
    def log_analyzed_documents(self, module_id: int, module_name: str, documents: List[dict]):
        """
        Registra los documentos que fueron analizados en un módulo.
        
        Args:
            module_id: ID del módulo
            module_name: Nombre del módulo
            documents: Lista de documentos analizados [{title, item_type, content, ...}]
        """
        self.analyzed_documents[module_id] = {
            'module_name': module_name,
            'documents': documents,
            'timestamp': datetime.now().isoformat(),
            'count': len(documents)
        }
        
        self.log_event(
            'RAG',
            f'📚 Documentos analizados registrados: {len(documents)} items en "{module_name}"',
            {
                'module_id': module_id,
                'module_name': module_name,
                'document_count': len(documents)
            }
        )
    
    def get_recent_events(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Obtiene eventos recientes, opcionalmente filtrando por tipo"""
        events = self.events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # Retornar los últimos N eventos
        return [e.to_dict() for e in events[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema"""
        return {
            'timestamp': datetime.now().isoformat(),
            'rag': self.rag_stats,
            'deepseek': self.deepseek_stats,
            'memory_db': self.memory_db_stats,
            'total_events': len(self.events),
            'event_types': {
                'RAG': len([e for e in self.events if e.event_type == 'RAG']),
                'DEEPSEEK': len([e for e in self.events if e.event_type == 'DEEPSEEK']),
                'EMBEDDING': len([e for e in self.events if e.event_type == 'EMBEDDING']),
                'MEMORY_DB': len([e for e in self.events if e.event_type == 'MEMORY_DB']),
                'ERROR': len([e for e in self.events if e.event_type == 'ERROR']),
            }
        }
    
    def get_analyzed_documents(self, module_id: Optional[int] = None) -> Dict[str, Any]:
        """Obtiene la lista de documentos analizados"""
        if module_id:
            return self.analyzed_documents.get(module_id, {})
        return self.analyzed_documents
    
    def clear_events(self):
        """Limpiar eventos (útil después de exportar)"""
        self.events = []


# Instancia global singleton
_debug_service = None

def get_debug_service() -> DebugService:
    """Factory para obtener la instancia de DebugService"""
    global _debug_service
    if _debug_service is None:
        _debug_service = DebugService()
    return _debug_service
