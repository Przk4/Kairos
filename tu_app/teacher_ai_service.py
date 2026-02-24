"""
Teacher AI Service — Generador de tareas potenciado con IA
Usa su propia API key (DEEPSEEK_TEACHER_API_KEY) para separar
el consumo de tokens del servicio de tutoría estudiantil.

Si DEEPSEEK_TEACHER_API_KEY no está configurada, usa DEEPSEEK_API_KEY como fallback.
"""

import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


TEACHER_SYSTEM_PROMPT = """Eres un experto en diseño instruccional y pedagogía universitaria.
Tu trabajo es ayudar a profesores a crear tareas educativas de alta calidad.

Cuando el profesor te describa una tarea, debes:
1. Estructurar la tarea de forma clara y profesional
2. Redactar instrucciones precisas para los estudiantes
3. Incluir criterios de evaluación implícitos
4. Asegurar que la tarea fomente el pensamiento crítico y el razonamiento
5. Usar un tono formal pero accesible para estudiantes universitarios

FORMATO DE RESPUESTA:
- Escribe SOLO la descripción de la tarea lista para publicar
- NO incluyas metadatos como "Título:", "Puntos:", "Fecha:" — eso lo configura el profesor aparte
- Usa formato claro con numeración, viñetas o secciones según sea apropiado
- Si el profesor pide ejercicios, numéralos claramente
- Si el profesor da instrucciones específicas (ej: "3 ejercicios", "razonamiento crítico"), respétalas al pie de la letra

Responde siempre en español."""


class TeacherAIService:
    """
    Servicio de IA dedicado para profesores.
    Separado del servicio de tutoría estudiantil para:
    - Control independiente de costos/tokens
    - System prompt especializado en diseño de tareas
    - Posibilidad de usar modelo diferente en el futuro
    """

    def __init__(self):
        # Prioridad: DEEPSEEK_TEACHER_API_KEY > DEEPSEEK_API_KEY
        self.api_key = os.getenv('DEEPSEEK_TEACHER_API_KEY') or os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("Ni DEEPSEEK_TEACHER_API_KEY ni DEEPSEEK_API_KEY están configuradas")

        try:
            import openai
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
        except ImportError:
            raise ImportError("openai library no instalada. pip install openai")

        self.model = "deepseek-chat"
        key_used = "DEEPSEEK_TEACHER_API_KEY" if os.getenv('DEEPSEEK_TEACHER_API_KEY') else "DEEPSEEK_API_KEY (fallback)"
        logger.info(f"TeacherAIService initialized with {key_used}")

    def generate_assignment(self, teacher_prompt: str, course_name: str = "", max_tokens: int = 2000) -> dict:
        """
        Genera una propuesta de tarea basada en la descripción del profesor.

        Args:
            teacher_prompt: Lo que el profesor escribió (ej: "simple, tres ejercicios, con razonamiento crítico")
            course_name: Nombre del curso para contexto
            max_tokens: Máximo de tokens en la respuesta

        Returns:
            {
                'description': str,      # La tarea generada
                'tokens_used': int,
                'processing_time': float,
                'model': str,
            }
        """
        try:
            user_message = teacher_prompt
            if course_name:
                user_message = f"Curso: {course_name}\n\n{teacher_prompt}"

            messages = [
                {"role": "system", "content": TEACHER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]

            start_time = time.time()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
            )

            elapsed = time.time() - start_time
            answer = response.choices[0].message.content
            tokens = response.usage.total_tokens

            logger.info(f"Teacher AI generated assignment: {tokens} tokens, {elapsed:.2f}s")

            return {
                'description': answer,
                'tokens_used': tokens,
                'processing_time': elapsed,
                'model': self.model,
            }

        except Exception as e:
            logger.error(f"TeacherAIService error: {e}")
            return {
                'description': f"Error generando tarea: {str(e)}",
                'tokens_used': 0,
                'processing_time': 0,
                'model': self.model,
            }


# Singleton
_teacher_ai_instance: Optional[TeacherAIService] = None


def get_teacher_ai_service() -> TeacherAIService:
    """Factory singleton para el servicio de IA del profesor."""
    global _teacher_ai_instance
    if _teacher_ai_instance is None:
        _teacher_ai_instance = TeacherAIService()
    return _teacher_ai_instance
