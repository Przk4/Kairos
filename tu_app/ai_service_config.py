"""
Servicio de IA Configurable - Soporta múltiples proveedores
Permite cambiar fácilmente entre: DeepSeek, Hugging Face, Gemini, Mock

Para cambiar de proveedor, modifica solo ACTIVE_PROVIDER al final del archivo
"""

import os
import time
import logging
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ============================================================================
# INTERFAZ BASE
# ============================================================================

class AIProvider(ABC):
    """Interfaz que todos los proveedores de IA deben implementar"""
    
    @abstractmethod
    def answer_question(
        self,
        question: str,
        context: List[dict],
        max_tokens: int = 1000
    ) -> dict:
        """
        Responde una pregunta basándose en contexto RAG.
        
        Returns:
            {
                'answer': str,
                'tokens_used': int,
                'processing_time': float,
                'model': str,
                'context_used': int,
            }
        """
        pass


# ============================================================================
# OPCIÓN 1: DEEPSEEK (Producción)
# ============================================================================

class DeepSeekProvider(AIProvider):
    """Proveedor oficial DeepSeek - Para usar cuando tengas API key"""
    
    SYSTEM_PROMPT = """Eres un tutor IA experto en educación. Tu objetivo es:

1. Ayudar a estudiantes a comprender conceptos basándose en el material del curso
2. Proporcionar respuestas claras y educativas
3. Fomentar el pensamiento crítico sin dar respuestas directas a tareas
4. Reformular conceptos si el estudiante no entiende
5. Indicar cuando un tema está fuera del alcance del curso

Siempre basa tus respuestas en el contexto proporcionado del material del curso.
Si la pregunta está fuera del contexto, dilo claramente."""
    
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY no configurada")
        
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
        except ImportError:
            raise ImportError("openai library no instalada. pip install openai")
        
        self.model = "deepseek-chat"
        logger.info("✅ DeepSeek Provider inicializado")
    
    def answer_question(
        self,
        question: str,
        context: List[dict],
        max_tokens: int = 1000
    ) -> dict:
        try:
            context_text = self._format_context(context)
            
            messages = [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"""Contexto del curso:
{context_text}

Pregunta del estudiante:
{question}

Por favor, responde basándote en el contexto proporcionado."""
                }
            ]
            
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
            )
            
            elapsed_time = time.time() - start_time
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            return {
                'answer': response_text,
                'tokens_used': tokens_used,
                'processing_time': elapsed_time,
                'model': self.model,
                'context_used': len(context),
            }
        
        except Exception as e:
            logger.error(f"DeepSeek error: {e}")
            return {
                'answer': f"Error: {str(e)}",
                'tokens_used': 0,
                'processing_time': 0,
                'model': self.model,
                'context_used': len(context),
            }
    
    def _format_context(self, context: List[dict]) -> str:
        """Formatea el contexto para enviar a DeepSeek"""
        if not context:
            return "No hay contexto disponible."
        
        lines = []
        for i, doc in enumerate(context, 1):
            content = doc.get('content', '')[:200]  # Primeros 200 chars
            metadata = doc.get('metadata', {})
            title = metadata.get('item_title', 'Sin título')
            relevance = doc.get('relevance_score', 0)
            
            lines.append(f"{i}. {title} (relevancia: {relevance:.2f})")
            lines.append(f"   {content}...\n")
        
        return "\n".join(lines)


# ============================================================================
# OPCIÓN 2: HUGGING FACE INFERENCE API (Gratuito - Testing)
# ============================================================================

class HuggingFaceProvider(AIProvider):
    """Proveedor Hugging Face - Gratuito con API key (free tier)"""
    
    def __init__(self):
        self.api_key = os.getenv('HUGGINGFACE_API_KEY')
        if not self.api_key:
            raise ValueError("HUGGINGFACE_API_KEY no configurada")
        
        self.model = "mistralai/Mistral-7B-Instruct-v0.1"
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model}"
        logger.info("✅ Hugging Face Provider inicializado")
    
    def answer_question(
        self,
        question: str,
        context: List[dict],
        max_tokens: int = 1000
    ) -> dict:
        try:
            import requests
            
            context_text = self._format_context(context)
            
            prompt = f"""Por favor responde la siguiente pregunta basándote ÚNICAMENTE en el contexto proporcionado.

Contexto:
{context_text}

Pregunta: {question}

Respuesta:"""
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": 0.7,
                }
            }
            
            start_time = time.time()
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            elapsed_time = time.time() - start_time
            
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                answer = result[0].get('generated_text', '').split('Respuesta:')[-1].strip()
            else:
                answer = str(result)
            
            # Estimar tokens (aproximadamente 1 token por 4 caracteres)
            tokens_estimated = len(prompt.split()) + len(answer.split())
            
            return {
                'answer': answer,
                'tokens_used': tokens_estimated,
                'processing_time': elapsed_time,
                'model': self.model,
                'context_used': len(context),
            }
        
        except Exception as e:
            logger.error(f"Hugging Face error: {e}")
            return {
                'answer': f"Error en Hugging Face: {str(e)}",
                'tokens_used': 0,
                'processing_time': 0,
                'model': self.model,
                'context_used': len(context),
            }
    
    def _format_context(self, context: List[dict]) -> str:
        if not context:
            return "No hay contexto disponible."
        
        lines = []
        for i, doc in enumerate(context, 1):
            content = doc.get('content', '')[:300]
            metadata = doc.get('metadata', {})
            title = metadata.get('item_title', 'Sin título')
            
            lines.append(f"{i}. {title}")
            lines.append(f"   {content}\n")
        
        return "\n".join(lines)


# ============================================================================
# OPCIÓN 3: MOCK/DEMO (Sin API - Solo para testing rápido)
# ============================================================================

class MockAIProvider(AIProvider):
    """Proveedor Mock - Responde basado en patrones, sin API"""
    
    def __init__(self):
        self.model = "mock-tutor"
        logger.info("⚠️  MockAI Provider inicializado - SOLO PARA TESTING")
    
    def answer_question(
        self,
        question: str,
        context: List[dict],
        max_tokens: int = 1000
    ) -> dict:
        start_time = time.time()
        
        # Respuesta basada en palabras clave
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['pitágoras', 'hipotenusa', 'triángulo']):
            answer = """El Teorema de Pitágoras establece que en un triángulo rectángulo, 
el cuadrado de la hipotenusa es igual a la suma de los cuadrados de los otros dos lados: a² + b² = c²

Basándome en el material del curso:
- Se utiliza para encontrar lados desconocidos en triángulos rectángulos
- Tiene aplicaciones en geometría, trigonometría y física
- Es uno de los teoremas más importantes de las matemáticas

¿Tienes alguna pregunta más específica sobre cómo aplicar este teorema?"""
        
        elif any(word in question_lower for word in ['cómo', 'qué', 'por qué', 'explicar']):
            answer = """Basándome en el material del curso que hemos analizado:

El tema que buscas aparece en varios documentos con información relacionada. 
Te recomiendo revisar los documentos del módulo para una comprensión más profunda.

¿Hay algún aspecto específico que quieras que explique?"""
        
        else:
            answer = f"""He analizado el contexto del curso y encontré {len(context)} documentos relevantes.

Basándome en el material disponible: {self._extract_summary(context)}

¿Necesitas que profundice en algún aspecto específico?"""
        
        elapsed_time = time.time() - start_time
        tokens_estimated = len(answer.split())
        
        return {
            'answer': answer,
            'tokens_used': tokens_estimated,
            'processing_time': elapsed_time,
            'model': self.model,
            'context_used': len(context),
        }
    
    def _extract_summary(self, context: List[dict]) -> str:
        if not context:
            return "No hay contexto disponible."
        
        items = []
        for doc in context[:2]:
            metadata = doc.get('metadata', {})
            title = metadata.get('item_title', 'Item')
            items.append(title)
        
        return f"Se encontraron documentos sobre: {', '.join(items)}"


# ============================================================================
# FACTOR DE SELECCIÓN
# ============================================================================

def get_ai_service(provider: Optional[str] = None) -> AIProvider:
    """
    Factory para obtener el proveedor de IA configurado.
    
    Args:
        provider: Nombre del proveedor ('deepseek', 'huggingface', 'mock')
                 Si es None, usa ACTIVE_PROVIDER
    
    Returns:
        Instancia del proveedor
    
    Ejemplo:
        # Usar proveedor por defecto
        ai = get_ai_service()
        
        # Cambiar temporalmente a Mock
        ai = get_ai_service('mock')
        
        # Cambiar a DeepSeek
        ai = get_ai_service('deepseek')
    """
    
    # Si no especificas, usa el configurado por defecto
    if provider is None:
        provider = ACTIVE_PROVIDER
    
    provider = provider.lower()
    
    if provider == 'deepseek':
        try:
            return DeepSeekProvider()
        except ValueError:
            logger.warning("DeepSeek no configurado, usando Mock")
            return MockAIProvider()
    
    elif provider == 'huggingface':
        try:
            return HuggingFaceProvider()
        except ValueError:
            logger.warning("Hugging Face no configurado, usando Mock")
            return MockAIProvider()
    
    elif provider == 'mock':
        return MockAIProvider()
    
    else:
        logger.warning(f"Proveedor desconocido: {provider}, usando Mock")
        return MockAIProvider()


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# 👇 CAMBIAR AQUÍ PARA USAR UN PROVEEDOR DIFERENTE 👇
ACTIVE_PROVIDER = "deepseek"  # Opciones: "deepseek", "huggingface", "mock"

# Explicación:
# "mock" = Responde sin API (perfect para testing hoy)
# "huggingface" = Gratis con API key (huggingface.co)
# "deepseek" = Producción (cuando tengas dinero)

# Después de cambiar, usa:
#   ai = get_ai_service()
#   response = ai.answer_question(question, context)

# ============================================================================

logger.info(f"🤖 Sistema de IA configurado para usar: {ACTIVE_PROVIDER.upper()}")
