# tu_app/ai_service.py
# WRAPPER - Este archivo ahora usa el sistema configurable de ai_service_config.py

import logging
from typing import List, Optional
from tu_app.ai_service_config import (
    ACTIVE_PROVIDER, 
    MockAIProvider,
    DeepSeekProvider,
    HuggingFaceProvider,
)
from tu_app.debug_service import get_debug_service

logger = logging.getLogger(__name__)


class DeepSeekAIService:
    """
    Servicio de IA wrapper - Ahora usa el sistema configurable.
    
    ¿Cómo cambiar de proveedor?
    Edita tu_app/ai_service_config.py y cambia ACTIVE_PROVIDER.
    
    Desde:
        ACTIVE_PROVIDER = "mock"
    Para:
        ACTIVE_PROVIDER = "deepseek"  (cuando tengas API key)
    
    ¡El resto del código no necesita cambios!
    """
    
    SYSTEM_PROMPT = """Eres un tutor IA experto en educación."""
    
    def __init__(self):
        """Inicializa el servicio usando el proveedor configurado"""
        # Instanciar el proveedor correcto basado en ACTIVE_PROVIDER
        provider_name = ACTIVE_PROVIDER.lower()
        
        if provider_name == "deepseek":
            try:
                self.provider = DeepSeekProvider()
            except ValueError:
                logger.warning("DeepSeek not available, falling back to Mock")
                self.provider = MockAIProvider()
        
        elif provider_name == "huggingface":
            try:
                self.provider = HuggingFaceProvider()
            except ValueError:
                logger.warning("Hugging Face not available, falling back to Mock")
                self.provider = MockAIProvider()
        
        else:
            # Default to Mock
            self.provider = MockAIProvider()
        
        self.model = self.provider.model
        logger.info(f"✅ DeepSeekAIService usando proveedor: {self.provider.__class__.__name__}")
    
    
    def answer_question(
        self,
        question: str,
        context: List[dict],
        user: Optional[object] = None,
        max_tokens: int = 1000
    ) -> dict:
        """
        Responde una pregunta basándose en contexto RAG.
        Este método delega al proveedor configurado.
        """
        debug_service = get_debug_service()
        
        try:
            # Delegar al proveedor configurado
            result = self.provider.answer_question(
                question=question,
                context=context,
                max_tokens=max_tokens
            )
            
            # Log a debug service
            debug_service.log_deepseek_call(
                prompt=question,
                response=result['answer'],
                tokens_used=result['tokens_used'],
                response_time_ms=result['processing_time'] * 1000
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error en answer_question: {e}")
            debug_service.log_error("AI_SERVICE", f"Error respondiendo pregunta", e)
            return {
                'answer': f"Error: {str(e)}",
                'tokens_used': 0,
                'processing_time': 0,
                'model': self.model,
                'context_used': len(context),
            }


def get_ai_service() -> DeepSeekAIService:
    """
    Factory para obtener instancia del servicio.
    Usa el proveedor configurado en ai_service_config.py
    
    NOTA: Esta función NO tiene recursión. Crea directamente 
    la instancia DeepSeekAIService sin loops.
    """
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = DeepSeekAIService()
    return _ai_service_instance


# Instancia global (singleton)
_ai_service_instance = None
