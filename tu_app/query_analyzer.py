# tu_app/query_analyzer.py
"""
Analizador inteligente de preguntas para optimizar RAG.
Usa el mismo modelo de embeddings (MiniLM) para clasificar preguntas
sin necesidad de APIs externas ni modelos adicionales.
"""

import re
import logging
from typing import Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    Analiza preguntas para determinar:
    - Tipo de pregunta (resumen, definición, comparación, etc.)
    - Número óptimo de fragmentos a recuperar
    - Palabras clave expandidas para búsqueda
    - Nivel de detalle requerido
    """
    
    # Preguntas ejemplo por categoría (para clasificación por similitud)
    QUERY_EXAMPLES = {
        'summary': [
            "dame un resumen del tema",
            "resúmeme el contenido",
            "haz un resumen de todo",
            "explica brevemente de qué trata",
            "cuáles son los puntos principales",
            "sintetiza la información",
            "qué temas se cubren",
            "dame una visión general",
        ],
        'definition': [
            "qué es",
            "qué significa",
            "cómo se define",
            "cuál es la definición de",
            "explica el concepto de",
            "define",
            "a qué se refiere",
        ],
        'comparison': [
            "cuál es la diferencia entre",
            "compara",
            "en qué se diferencian",
            "qué tienen en común",
            "similitudes y diferencias",
            "versus",
            "comparado con",
        ],
        'list': [
            "cuáles son los tipos de",
            "enumera",
            "lista los",
            "menciona los",
            "cuántos hay",
            "qué elementos",
            "cuáles son las características",
            "dame ejemplos de",
        ],
        'specific': [
            "en qué página",
            "dónde dice",
            "cómo se calcula",
            "cuál es la fórmula",
            "qué paso",
            "cuándo",
            "quién",
            "por qué",
        ],
        'explanation': [
            "explica cómo",
            "por qué ocurre",
            "cómo funciona",
            "cuál es el proceso",
            "explícame",
            "describe el procedimiento",
            "cómo se hace",
        ],
    }
    
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
    
    def __init__(self, embedding_model=None):
        """
        Inicializa el analizador.
        
        Args:
            embedding_model: Modelo de SentenceTransformer (opcional, se carga si no se proporciona)
        """
        self.embedding_model = embedding_model
        self._example_embeddings = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Inicialización lazy de embeddings de ejemplos."""
        if self._initialized:
            return
        
        if self.embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                logger.info("QueryAnalyzer: Loaded embedding model")
            except Exception as e:
                logger.warning(f"QueryAnalyzer: Could not load embedding model: {e}")
                self._initialized = True
                return
        
        # Pre-calcular embeddings de ejemplos
        self._example_embeddings = {}
        for query_type, examples in self.QUERY_EXAMPLES.items():
            embeddings = self.embedding_model.encode(examples)
            self._example_embeddings[query_type] = embeddings
        
        logger.info(f"QueryAnalyzer: Pre-computed embeddings for {len(self._example_embeddings)} query types")
        self._initialized = True
    
    def _classify_by_similarity(self, question: str) -> Tuple[str, float]:
        """
        Clasifica la pregunta comparando con ejemplos usando similitud coseno.
        
        Returns:
            Tuple de (query_type, confidence)
        """
        self._ensure_initialized()
        
        if self._example_embeddings is None:
            return 'general', 0.0
        
        try:
            question_embedding = self.embedding_model.encode(question)
            
            best_type = 'general'
            best_score = 0.0
            
            for query_type, example_embeddings in self._example_embeddings.items():
                # Calcular similitud con cada ejemplo del tipo
                similarities = []
                for emb in example_embeddings:
                    # Similitud coseno
                    similarity = np.dot(question_embedding, emb) / (
                        np.linalg.norm(question_embedding) * np.linalg.norm(emb) + 1e-8
                    )
                    similarities.append(similarity)
                
                # Tomar el máximo (mejor match con algún ejemplo del tipo)
                max_similarity = max(similarities)
                
                if max_similarity > best_score:
                    best_score = max_similarity
                    best_type = query_type
            
            return best_type, float(best_score)
        
        except Exception as e:
            logger.error(f"Error in similarity classification: {e}")
            return 'general', 0.0
    
    def _classify_by_keywords(self, question: str) -> Tuple[str, float]:
        """
        Clasifica usando patrones de palabras clave como refuerzo.
        
        Returns:
            Tuple de (query_type, confidence)
        """
        question_lower = question.lower()
        
        matches = {}
        for query_type, pattern in self.KEYWORD_PATTERNS.items():
            if re.search(pattern, question_lower, re.IGNORECASE):
                # Contar matches
                found = re.findall(pattern, question_lower, re.IGNORECASE)
                matches[query_type] = len(found)
        
        if matches:
            best_type = max(matches, key=matches.get)
            # Normalizar confianza (1-3 matches = 0.5-0.9)
            confidence = min(0.5 + matches[best_type] * 0.2, 0.9)
            return best_type, confidence
        
        return 'general', 0.0
    
    def _detect_detail_level(self, question: str) -> str:
        """Detecta el nivel de detalle solicitado."""
        question_lower = question.lower()
        
        for level, patterns in self.DETAIL_MODIFIERS.items():
            for pattern in patterns:
                if re.search(pattern, question_lower, re.IGNORECASE):
                    return level
        
        return 'normal'
    
    def _extract_search_terms(self, question: str) -> List[str]:
        """
        Extrae términos clave para búsqueda expandida.
        """
        # Remover palabras vacías comunes
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
        
        # Tokenizar y filtrar
        words = re.findall(r'\b[a-záéíóúñü]+\b', question.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        # Mantener orden pero eliminar duplicados
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords
    
    def _calculate_optimal_fragments(self, query_type: str, detail_level: str, 
                                     question_length: int) -> int:
        """
        Calcula el número óptimo de fragmentos basado en múltiples factores.
        """
        config = self.FRAGMENTS_CONFIG.get(query_type, self.FRAGMENTS_CONFIG['general'])
        base = config['default']
        
        # Ajustar por nivel de detalle
        if detail_level == 'brief':
            base = max(config['min'], base - 2)
        elif detail_level == 'comprehensive':
            base = min(config['max'], base + 3)
        
        # Ajustar por longitud de pregunta (preguntas más largas = más específicas = menos fragmentos)
        if question_length > 100:
            base = max(config['min'], base - 1)
        elif question_length < 30:
            base = min(config['max'], base + 1)
        
        return base
    
    def analyze(self, question: str) -> Dict:
        """
        Analiza una pregunta y retorna configuración óptima para RAG.
        
        Args:
            question: La pregunta del usuario
            
        Returns:
            Dict con:
            - query_type: Tipo de pregunta detectado
            - num_fragments: Número óptimo de fragmentos a recuperar
            - search_terms: Términos clave para búsqueda
            - detail_level: Nivel de detalle ('brief', 'normal', 'comprehensive')
            - confidence: Confianza en la clasificación (0-1)
            - reasoning: Explicación de la decisión
        """
        if not question or not question.strip():
            return {
                'query_type': 'general',
                'num_fragments': 5,
                'search_terms': [],
                'detail_level': 'normal',
                'confidence': 0.0,
                'reasoning': 'Pregunta vacía'
            }
        
        question = question.strip()
        
        # Clasificación híbrida: embeddings + keywords
        emb_type, emb_conf = self._classify_by_similarity(question)
        kw_type, kw_conf = self._classify_by_keywords(question)
        
        # Combinar clasificaciones
        if kw_conf > 0.6:
            # Keywords tienen prioridad si son fuertes
            query_type = kw_type
            confidence = kw_conf
            method = 'keywords'
        elif emb_conf > 0.5:
            # Usar clasificación por embeddings
            query_type = emb_type
            confidence = emb_conf
            method = 'embeddings'
        elif kw_conf > 0 and emb_conf > 0:
            # Ambos detectaron algo, usar el de mayor confianza
            if emb_conf >= kw_conf:
                query_type = emb_type
                confidence = emb_conf
                method = 'embeddings'
            else:
                query_type = kw_type
                confidence = kw_conf
                method = 'keywords'
        else:
            query_type = 'general'
            confidence = 0.3
            method = 'default'
        
        # Detectar nivel de detalle
        detail_level = self._detect_detail_level(question)
        
        # Extraer términos de búsqueda
        search_terms = self._extract_search_terms(question)
        
        # Calcular número óptimo de fragmentos
        num_fragments = self._calculate_optimal_fragments(
            query_type, 
            detail_level, 
            len(question)
        )
        
        # Generar razonamiento
        reasoning = f"Tipo '{query_type}' detectado por {method} (conf: {confidence:.2f}). "
        reasoning += f"Nivel de detalle: {detail_level}. "
        reasoning += f"Fragmentos: {num_fragments}."
        
        return {
            'query_type': query_type,
            'num_fragments': num_fragments,
            'search_terms': search_terms,
            'detail_level': detail_level,
            'confidence': round(confidence, 3),
            'reasoning': reasoning,
            '_debug': {
                'embedding_classification': (emb_type, round(emb_conf, 3)),
                'keyword_classification': (kw_type, round(kw_conf, 3)),
                'method_used': method,
            }
        }


# Singleton para reutilizar
_query_analyzer_instance = None


def get_query_analyzer(embedding_model=None) -> QueryAnalyzer:
    """
    Obtiene instancia singleton del QueryAnalyzer.
    
    Args:
        embedding_model: Modelo de embeddings (opcional, usa el del RAGService si está disponible)
    """
    global _query_analyzer_instance
    
    if _query_analyzer_instance is None:
        _query_analyzer_instance = QueryAnalyzer(embedding_model)
    
    return _query_analyzer_instance
