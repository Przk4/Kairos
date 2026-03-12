# tu_app/query_analyzer.py
"""
Analizador ligero de preguntas para optimizar RAG.

Versión optimizada: usa solo Ollama local (qwen2.5:1.5b) para extraer
términos clave y generar sinónimos/equivalentes para mejorar la búsqueda.
Sin embeddings en tiempo de query — solo keyword matching rápido.

Fallback: extracción de términos por regex si Ollama no está disponible.
"""

import json
import os
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    Analiza preguntas de forma ligera:
    - Tipo de pregunta detectado por keywords (sin embeddings)
    - Términos clave extraídos + sinónimos generados por Ollama local
    - Número óptimo de fragmentos a recuperar
    - Nivel de detalle requerido
    """

    # Configuración de fragmentos por tipo
    FRAGMENTS_CONFIG = {
        'summary': {'min': 8, 'max': 15, 'default': 10},
        'definition': {'min': 2, 'max': 5, 'default': 3},
        'comparison': {'min': 4, 'max': 8, 'default': 6},
        'list': {'min': 5, 'max': 12, 'default': 8},
        'specific': {'min': 2, 'max': 4, 'default': 3},
        'explanation': {'min': 4, 'max': 8, 'default': 5},
        'general': {'min': 3, 'max': 7, 'default': 5},
    }

    # Palabras clave que refuerzan cada tipo
    KEYWORD_PATTERNS = {
        'summary': r'\b(resumen|resume|resúmeme|sintetiza|síntesis|visión general|puntos principales|temas|overview)\b',
        'definition': r'\b(qué es|qué significa|define|definición|concepto|significa|refiere)\b',
        'comparison': r'\b(diferencia|compara|comparación|similar|versus|vs|común|distintos?)\b',
        'list': r'\b(cuáles|enumera|lista|tipos|elementos|características|ejemplos|menciona|cuántos)\b',
        'specific': r'\b(dónde|cuándo|quién|página|fórmula|calcul|exactamente|específicamente)\b',
        'explanation': r'\b(cómo|explica|proceso|funciona|procedimiento|pasos|método)\b',
    }

    # Modificadores de detalle
    DETAIL_MODIFIERS = {
        'brief': [
            r'\b(breve|brevemente|corto|rápido|simple|básico)\b',
            r'\b(en pocas palabras|sin detalles)\b',
        ],
        'comprehensive': [
            r'\b(detallado|detalle|completo|extenso|profundo|todo)\b',
            r'\b(a fondo|exhaustivo|amplio)\b',
        ],
    }

    # Bilingual term expansion
    BILINGUAL_TERMS = {
        'resumen': ['summary', 'overview', 'recap'],
        'summary': ['resumen'],
        'overview': ['resumen'],
        'definición': ['definition'],
        'definition': ['definición'],
        'comparación': ['comparison'],
        'comparison': ['comparación'],
        'ejemplo': ['example'],
        'example': ['ejemplo'],
        'conclusión': ['conclusion'],
        'conclusion': ['conclusión'],
        'objetivo': ['objective', 'goal', 'aim'],
        'objective': ['objetivo'],
        'goal': ['objetivo', 'meta'],
        'principio': ['principle'],
        'principle': ['principio'],
        'proceso': ['process'],
        'process': ['proceso'],
        'ventaja': ['advantage', 'benefit'],
        'advantage': ['ventaja'],
        'desventaja': ['disadvantage'],
        'disadvantage': ['desventaja'],
        'característica': ['characteristic', 'feature'],
        'characteristic': ['característica'],
        'todo': ['all', 'everything', 'overview'],
    }

    def __init__(self):
        self._ai_client = None
        self._ai_available = None
        self._ollama_model = os.getenv('OLLAMA_ANALYZER_MODEL', 'qwen2.5:1.5b')
        self._connect_timeout = float(os.getenv('OLLAMA_CONNECT_TIMEOUT', '2.0'))
        self._request_timeout = float(os.getenv('OLLAMA_ANALYZER_TIMEOUT', '2.5'))

    # ------------------------------------------------------------------
    # Keyword-only classification (no embeddings, no AI call)
    # ------------------------------------------------------------------

    def _classify_by_keywords(self, question: str) -> Tuple[str, float]:
        question_lower = question.lower()
        matches = {}
        for query_type, pattern in self.KEYWORD_PATTERNS.items():
            found = re.findall(pattern, question_lower, re.IGNORECASE)
            if found:
                matches[query_type] = len(found)

        if matches:
            best_type = max(matches, key=matches.get)
            confidence = min(0.5 + matches[best_type] * 0.2, 0.9)
            return best_type, confidence

        return 'general', 0.3

    # ------------------------------------------------------------------
    # Ollama-only AI for term extraction + synonym generation
    # ------------------------------------------------------------------

    def _get_ollama_client(self):
        """Lazy-init: connect to Ollama only (local, free, fast)."""
        if self._ai_available is False:
            return None
        if self._ai_client is not None:
            return self._ai_client
        try:
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            import urllib.request
            req = urllib.request.Request(f"{ollama_url}/api/tags", method='GET')
            with urllib.request.urlopen(req, timeout=self._connect_timeout) as resp:
                if resp.status == 200:
                    import openai as _openai
                    self._ai_client = _openai.OpenAI(
                        api_key='ollama',
                        base_url=f"{ollama_url}/v1",
                        timeout=self._request_timeout,
                    )
                    self._ai_available = True
                    logger.info("QueryAnalyzer: using Ollama (local, lightweight)")
                    return self._ai_client
        except Exception:
            pass

        self._ai_available = False
        logger.info("QueryAnalyzer: Ollama not available, using keyword fallback")
        return None

    def _extract_terms_ai(self, question: str) -> Optional[List[str]]:
        """
        Use Ollama local to extract key terms AND generate
        equivalent/synonym terms for better keyword matching.
        Returns expanded list of search terms, or None on failure.
        """
        client = self._get_ollama_client()
        if not client:
            return None
        try:
            prompt = (
                'De la siguiente pregunta de estudiante, extrae los conceptos clave '
                'y genera sinónimos o términos equivalentes para cada uno.\n\n'
                'Devuelve SOLO un JSON array con todos los términos (originales + equivalentes).\n'
                'Máximo 10 términos en total. Sin stopwords ni verbos genéricos.\n\n'
                'Ejemplos:\n'
                '- "qué es kaizen" → ["kaizen", "mejora continua", "continuous improvement"]\n'
                '- "diferencia entre ADN y ARN" → ["ADN", "ARN", "DNA", "RNA", "ácido desoxirribonucleico", "ácido ribonucleico"]\n'
                '- "cómo funciona la fotosíntesis" → ["fotosíntesis", "photosynthesis", "cloroplasto", "chloroplast", "luz solar"]\n'
                '- "resume el tema de derivadas" → ["derivadas", "derivatives", "diferenciación", "differentiation", "tasa de cambio"]\n\n'
                f'Pregunta: {question}\n\n'
                'JSON array:'
            )

            response = client.chat.completions.create(
                model=self._ollama_model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=150,
                temperature=0.1,
            )

            text = response.choices[0].message.content.strip()
            # Strip markdown fences
            if text.startswith('```'):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

            terms = json.loads(text)
            if isinstance(terms, list):
                terms = [str(t).strip() for t in terms if t and str(t).strip()][:10]
                logger.info(f"QueryAnalyzer AI terms: {terms}")
                return terms

        except Exception as e:
            logger.warning(f"QueryAnalyzer AI term extraction failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_detail_level(self, question: str) -> str:
        question_lower = question.lower()
        for level, patterns in self.DETAIL_MODIFIERS.items():
            for pattern in patterns:
                if re.search(pattern, question_lower, re.IGNORECASE):
                    return level
        return 'normal'

    def _expand_bilingual(self, terms: List[str]) -> List[str]:
        """Expand search terms with bilingual translations."""
        expanded = list(terms)
        seen = {t.lower() for t in terms}
        for term in terms:
            for translation in self.BILINGUAL_TERMS.get(term.lower(), []):
                if translation.lower() not in seen:
                    expanded.append(translation)
                    seen.add(translation.lower())
        return expanded

    def _extract_search_terms(self, question: str) -> List[str]:
        """Regex-based fallback: extract keywords from question."""
        stopwords = {
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para',
            'que', 'qué', 'cual', 'cuál', 'como', 'cómo',
            'es', 'son', 'está', 'están', 'fue', 'fueron',
            'me', 'te', 'se', 'le', 'lo', 'nos',
            'y', 'o', 'pero', 'si', 'no',
            'este', 'esta', 'estos', 'estas', 'ese', 'esa',
            'mi', 'tu', 'su', 'nuestro', 'muy', 'más',
            'dame', 'dime', 'explica', 'explícame', 'haz', 'hazme',
        }
        words = re.findall(r'\b[a-záéíóúñü]+\b', question.lower())
        seen = set()
        unique = []
        for w in words:
            if w not in stopwords and len(w) > 2 and w not in seen:
                seen.add(w)
                unique.append(w)
        return unique

    def _calculate_optimal_fragments(self, query_type: str, detail_level: str,
                                     question_length: int) -> int:
        config = self.FRAGMENTS_CONFIG.get(query_type, self.FRAGMENTS_CONFIG['general'])
        base = config['default']
        if detail_level == 'brief':
            base = max(config['min'], base - 2)
        elif detail_level == 'comprehensive':
            base = min(config['max'], base + 3)
        if question_length > 100:
            base = max(config['min'], base - 1)
        elif question_length < 30:
            base = min(config['max'], base + 1)
        return base

    # ------------------------------------------------------------------
    # Main analysis method
    # ------------------------------------------------------------------

    def analyze(self, question: str) -> Dict:
        """
        Analiza una pregunta y retorna configuración óptima para RAG.

        Flow ligero:
        1. Clasificar tipo por keywords (regex, instantáneo)
        2. Extraer términos + sinónimos con Ollama local (rápido, ~200ms)
        3. Si Ollama no disponible, extraer por regex + expandir bilingüe
        4. Calcular fragmentos óptimos
        """
        if not question or not question.strip():
            return {
                'query_type': 'general',
                'num_fragments': 5,
                'search_terms': [],
                'detail_level': 'normal',
                'confidence': 0.0,
                'reasoning': 'Pregunta vacía',
            }

        question = question.strip()
        question_lower = question.lower()

        # --- 1. Classify by keywords (instant, no AI/embeddings) ---
        query_type, confidence = self._classify_by_keywords(question)
        detail_level = self._detect_detail_level(question)

        # --- 2. Extract terms: try Ollama first, fallback to regex ---
        ai_terms = self._extract_terms_ai(question)
        if ai_terms:
            search_terms = ai_terms
            method = 'ollama'
        else:
            search_terms = self._extract_search_terms(question)
            search_terms = self._expand_bilingual(search_terms)
            method = 'keywords'

        reasoning = (
            f"Tipo '{query_type}' (conf: {confidence:.2f}). "
            f"Términos por {method}: {search_terms[:5]}."
        )

        # --- 3. Optimal fragment count ---
        num_fragments = self._calculate_optimal_fragments(
            query_type, detail_level, len(question)
        )

        # --- 4. Special-case: 'todo' ---
        importance_weight = None
        if re.search(r'\btodo\b|\btodas?\b|\btodo el\b|\btodo el contenido\b|\btodo el tema\b',
                      question_lower, re.IGNORECASE):
            detail_level = 'comprehensive'
            summary_cfg = self.FRAGMENTS_CONFIG['summary']
            num_fragments = summary_cfg['max']  # 15
            importance_weight = 0.40

        ret = {
            'query_type': query_type,
            'num_fragments': num_fragments,
            'search_terms': search_terms,
            'detail_level': detail_level,
            'confidence': round(confidence, 3),
            'reasoning': reasoning,
        }
        if importance_weight is not None:
            ret['importance_weight'] = importance_weight
        return ret


# Singleton
_query_analyzer_instance = None


def get_query_analyzer(embedding_model=None) -> QueryAnalyzer:
    """
    Obtiene instancia singleton del QueryAnalyzer.
    embedding_model se ignora en la versión ligera (compatibilidad).
    """
    global _query_analyzer_instance
    if _query_analyzer_instance is None:
        _query_analyzer_instance = QueryAnalyzer()
    return _query_analyzer_instance
