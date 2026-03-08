# tu_app/query_analyzer.py
"""
Analizador inteligente de preguntas para optimizar RAG.
Usa el mismo modelo de embeddings (MiniLM) para clasificar preguntas
sin necesidad de APIs externas ni modelos adicionales.
"""

import json
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
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
        self._ai_client = None
        self._ai_available = None
        self._ai_backend = None  # 'ollama' or 'deepseek'
    
    def _ensure_initialized(self):
        """Inicialización lazy de embeddings de ejemplos."""
        if self._initialized:
            return
        
        if self.embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
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

    # ------------------------------------------------------------------
    # AI-based classification (primary method)
    # ------------------------------------------------------------------

    def _get_ai_client(self):
        """Lazy-init: try Ollama (free, local) first, then DeepSeek."""
        if self._ai_available is False:
            return None
        if self._ai_client is not None:
            return self._ai_client
        try:
            import openai as _openai

            # --- 1. Try Ollama (local, no tokens) ---
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            try:
                import urllib.request
                req = urllib.request.Request(f"{ollama_url}/api/tags", method='GET')
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        self._ai_client = _openai.OpenAI(
                            api_key='ollama',
                            base_url=f"{ollama_url}/v1",
                        )
                        self._ai_backend = 'ollama'
                        self._ai_available = True
                        logger.info("QueryAnalyzer: using Ollama (local)")
                        return self._ai_client
            except Exception:
                pass

            # --- 2. Fallback: DeepSeek ---
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                self._ai_available = False
                return None
            self._ai_client = _openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )
            self._ai_backend = 'deepseek'
            self._ai_available = True
            logger.info("QueryAnalyzer: using DeepSeek (remote)")
            return self._ai_client
        except Exception as e:
            logger.warning(f"QueryAnalyzer: AI client init failed: {e}")
            self._ai_available = False
            return None

    def _classify_by_ai(self, question: str) -> Optional[Dict]:
        """
        Call DeepSeek to extract query_type, search_terms, detail_level,
        confidence and reasoning.  Returns *None* on any failure so the
        caller can fall back to the embedding/keyword hybrid.
        """
        client = self._get_ai_client()
        if not client:
            return None
        try:
            prompt = (
                'Analiza esta pregunta de estudiante y devuelve SOLO un JSON '
                'válido con esta estructura exacta:\n\n'
                '{\n'
                '  "query_type": "summary|definition|comparison|list|specific|explanation|general",\n'
                '  "search_terms": ["término1", "término2"],\n'
                '  "detail_level": "brief|normal|comprehensive",\n'
                '  "confidence": 0.85,\n'
                '  "reasoning": "Breve explicación"\n'
                '}\n\n'
                'Reglas para search_terms:\n'
                '- Extrae SOLO palabras o frases que aparecen LITERALMENTE en la pregunta\n'
                '- NO inventes sinónimos, traducciones ni términos relacionados\n'
                '- Extrae 1-5 conceptos clave presentes en la pregunta\n'
                '- El primer término debe ser el concepto principal\n'
                '- NO incluyas stopwords, verbos genéricos ni palabras comunes\n'
                '- Ejemplo: "qué es kaizen" → ["kaizen"]\n'
                '- Ejemplo: "diferencia entre ADN y ARN" → ["ADN", "ARN"]\n'
                '- Ejemplo: "cómo funciona la fotosíntesis" → ["fotosíntesis"]\n\n'
                f'Pregunta: {question}\n\n'
                'JSON:'
            )

            model = 'qwen2.5:1.5b' if self._ai_backend == 'ollama' else 'deepseek-chat'

            response = client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=200,
                temperature=0.1,
            )

            text = response.choices[0].message.content.strip()
            # Strip possible markdown fences
            if text.startswith('```'):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

            result = json.loads(text)

            # --- Validate / sanitise ---
            valid_types = {
                'summary', 'definition', 'comparison',
                'list', 'specific', 'explanation', 'general',
            }
            if result.get('query_type') not in valid_types:
                result['query_type'] = 'general'

            if result.get('detail_level') not in {'brief', 'normal', 'comprehensive'}:
                result['detail_level'] = 'normal'

            result['confidence'] = max(0.0, min(1.0, float(result.get('confidence', 0.5))))
            result['search_terms'] = [str(t) for t in result.get('search_terms', [])][:5]
            result.setdefault('reasoning', '')

            result['_backend'] = self._ai_backend or 'unknown'
            logger.info(
                f"QueryAnalyzer AI ({result['_backend']}): type={result['query_type']}, "
                f"terms={result['search_terms']}, conf={result['confidence']}"
            )
            return result

        except Exception as e:
            logger.warning(f"QueryAnalyzer AI classification failed: {e}")
            return None

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

        # --- 1. Primary: AI-based classification ---
        ai_result = self._classify_by_ai(question)

        # --- Always run embedding+keyword analysis for debug ---
        emb_type, emb_conf = self._classify_by_similarity(question)
        kw_type, kw_conf = self._classify_by_keywords(question)
        fallback_search_terms = self._extract_search_terms(question)
        fallback_detail_level = self._detect_detail_level(question)

        _debug = {
            'embedding_classification': {'type': emb_type, 'confidence': round(emb_conf, 3)},
            'keyword_classification': {'type': kw_type, 'confidence': round(kw_conf, 3)},
            'fallback_search_terms': fallback_search_terms,
            'fallback_detail_level': fallback_detail_level,
        }

        if ai_result:
            query_type = ai_result['query_type']
            search_terms = ai_result['search_terms']
            detail_level = ai_result['detail_level']
            confidence = ai_result['confidence']
            reasoning = ai_result.get('reasoning', '')
            method = 'ai'
            _debug['method_used'] = 'ai'
            _debug['ai_backend'] = ai_result.get('_backend', 'unknown')
            _debug['ai_result'] = {
                'query_type': ai_result['query_type'],
                'search_terms': ai_result['search_terms'],
                'detail_level': ai_result['detail_level'],
                'confidence': ai_result['confidence'],
                'reasoning': ai_result.get('reasoning', ''),
            }
        else:
            # --- Fallback: embedding + keyword hybrid ---
            if kw_conf > 0.6:
                query_type = kw_type
                confidence = kw_conf
                method = 'keywords'
            elif emb_conf > 0.5:
                query_type = emb_type
                confidence = emb_conf
                method = 'embeddings'
            elif kw_conf > 0 and emb_conf > 0:
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

            detail_level = fallback_detail_level
            search_terms = fallback_search_terms
            reasoning = (
                f"Tipo '{query_type}' detectado por {method} (conf: {confidence:.2f}). "
                f"Nivel de detalle: {detail_level}."
            )
            _debug['method_used'] = method

        # --- 3. Optimal fragment count (always from config table) ---
        num_fragments = self._calculate_optimal_fragments(
            query_type, detail_level, len(question)
        )

        return {
            'query_type': query_type,
            'num_fragments': num_fragments,
            'search_terms': search_terms,
            'detail_level': detail_level,
            'confidence': round(confidence, 3),
            'reasoning': reasoning,
            '_debug': _debug,
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
