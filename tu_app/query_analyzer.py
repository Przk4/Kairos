# tu_app/query_analyzer.py
"""Analizador ligero de preguntas para optimizar RAG con keywords y reglas."""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    Analiza preguntas de forma ligera:
    - Tipo de pregunta detectado por keywords (sin embeddings)
    - Términos clave extraídos por regex y frases literales entre comillas
    - Número óptimo de fragmentos a recuperar
    - Nivel de detalle requerido
    """

    # Configuración de fragmentos por tipo
    FRAGMENTS_CONFIG = {
        'summary': {'min': 5, 'max': 10, 'default': 7},
        'definition': {'min': 2, 'max': 4, 'default': 3},
        'comparison': {'min': 3, 'max': 6, 'default': 5},
        'list': {'min': 4, 'max': 8, 'default': 6},
        'specific': {'min': 2, 'max': 4, 'default': 3},
        'explanation': {'min': 3, 'max': 7, 'default': 5},
        'general': {'min': 3, 'max': 6, 'default': 5},
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

    def _extract_quoted_terms(self, question: str) -> List[str]:
        literals = []
        for match in re.finditer(r'"([^"\n]+)"|“([^”\n]+)”', question):
            literal = (match.group(1) or match.group(2) or '').strip()
            if literal and literal.lower() not in {item.lower() for item in literals}:
                literals.append(literal)
        return literals

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
        2. Extraer términos por regex
        3. Preservar frases literales entre comillas
        4. Expandir términos bilingües
        5. Calcular fragmentos óptimos
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

        # --- 2. Extract terms using keywords + quoted literals ---
        quoted_terms = self._extract_quoted_terms(question)
        search_terms = quoted_terms + self._extract_search_terms(question)
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
            num_fragments = summary_cfg['max']  # 10
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
