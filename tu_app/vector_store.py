# tu_app/vector_store.py
"""
Generic vector store for Kairos.

Domain-agnostic: no Canvas knowledge, no Django models.
Can be used anywhere in the project that needs to store and search embeddings:

    from tu_app.vector_store import get_vector_store

    vs = get_vector_store()
    vs.upsert("my_collection", ["text..."], [{"source": "notes"}])
    results = vs.search("my_collection", "pregunta del usuario")

See VectorStore docstring for the full public API.
"""

import os
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB (optional — graceful fallback to in-memory + JSON)
# ---------------------------------------------------------------------------
try:
    import chromadb
    _CHROMADB_AVAILABLE = True
except Exception as _e:
    logger.warning(f"ChromaDB not available, using in-memory fallback: {_e}")
    _CHROMADB_AVAILABLE = False
    chromadb = None

# ---------------------------------------------------------------------------
# Default embedding model
# ---------------------------------------------------------------------------
_DEFAULT_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


class VectorStore:
    """
    General-purpose vector store backed by ChromaDB (or in-memory/JSON fallback).

    Public API
    ----------
    upsert(collection, documents, metadatas, ids, embeddings)
        Add or replace documents in a collection.

    search(collection, query, top_k, query_type, importance_weight, where)
        Semantic search.  Returns list of dicts with keys:
        content, metadata, relevance_score, importance_score, combined_score.

    collection_exists(collection) -> bool
    collection_count(collection) -> int
    delete_collection(collection)

    chunk_sliding(text, chunk_size, overlap) -> List[str]
    chunk_semantic(text, max_chunk_size, similarity_threshold) -> List[str]

    encode(texts) -> List[List[float]]
        Expose the embedding model publicly so callers can pre-compute vectors.
    """

    IMPORTANCE_WEIGHTS: Dict[str, float] = {
        'summary':     0.40,
        'definition':  0.20,
        'comparison':  0.25,
        'list':        0.30,
        'specific':    0.10,
        'explanation': 0.20,
        'general':     0.15,
    }

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        json_dir: Optional[str] = None,
        model_name: str = _DEFAULT_MODEL,
    ):
        """
        Parameters
        ----------
        persist_dir : str or None
            Directory for ChromaDB persistent storage.
            Defaults to ``<cwd>/.chroma_db``.
        json_dir : str or None
            Directory for JSON fallback storage.
            Defaults to ``<cwd>/.embeddings``.
        model_name : str
            HuggingFace sentence-transformer model identifier.
        """
        self.persist_dir = persist_dir or os.path.join(os.getcwd(), '.chroma_db')
        self.json_dir = json_dir or os.path.join(os.getcwd(), '.embeddings')
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        Path(self.json_dir).mkdir(parents=True, exist_ok=True)

        self.model_name = model_name
        self.embedding_model = SentenceTransformer(model_name)

        # In-memory store (populated from JSON on init; used as sole backend
        # when ChromaDB is unavailable)
        self._memory: Dict[str, dict] = {}
        self._load_json_store()

        # Try ChromaDB
        self.client = None
        self.using_chromadb = False
        if _CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=self.persist_dir)
                self.using_chromadb = True
                logger.info(f"[VectorStore] ChromaDB ready at {self.persist_dir}")
            except Exception as e:
                logger.warning(f"[VectorStore] ChromaDB init failed, using memory: {e}")

    # ------------------------------------------------------------------
    # Public API — storage
    # ------------------------------------------------------------------

    def upsert(
        self,
        collection: str,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> int:
        """
        Add (or replace by id) documents in *collection*.

        Returns
        -------
        int  Number of documents stored.
        """
        if not documents:
            return 0

        metas = metadatas or [{} for _ in documents]
        doc_ids = ids or [f"{collection}_{i}" for i in range(len(documents))]
        vecs = embeddings or self._encode(documents)

        if self.using_chromadb and self.client:
            col = self.client.get_or_create_collection(
                name=collection,
                metadata={"hnsw:space": "cosine"},
            )
            # Upsert in batches of 500
            batch = 500
            for start in range(0, len(documents), batch):
                col.upsert(
                    ids=doc_ids[start:start + batch],
                    embeddings=vecs[start:start + batch],
                    documents=documents[start:start + batch],
                    metadatas=metas[start:start + batch],
                )
        else:
            # In-memory: proper upsert — append new, replace existing by id
            col = self._memory.setdefault(collection, {
                'ids': [], 'documents': [], 'embeddings': [], 'metadatas': [],
            })
            id_index = {doc_id: i for i, doc_id in enumerate(col['ids'])}
            for doc_id, doc, vec, meta in zip(doc_ids, documents, vecs, metas):
                if doc_id in id_index:
                    idx = id_index[doc_id]
                    col['documents'][idx] = doc
                    col['embeddings'][idx] = vec
                    col['metadatas'][idx] = meta
                else:
                    col['ids'].append(doc_id)
                    col['documents'].append(doc)
                    col['embeddings'].append(vec)
                    col['metadatas'].append(meta)
            self._save_json_store(collection)

        logger.info(f"[VectorStore] upsert {len(documents)} docs into '{collection}'")
        return len(documents)

    def delete_collection(self, collection: str) -> None:
        """Delete all documents in *collection*."""
        if self.using_chromadb and self.client:
            try:
                self.client.delete_collection(collection)
            except Exception:
                pass
        self._memory.pop(collection, None)
        p = Path(self.json_dir) / f"{collection}.json"
        if p.exists():
            p.unlink()
        logger.info(f"[VectorStore] deleted collection '{collection}'")

    # ------------------------------------------------------------------
    # Public API — retrieval
    # ------------------------------------------------------------------

    def search(
        self,
        collection: str,
        query: str,
        top_k: int = 5,
        query_type: str = 'general',
        importance_weight: Optional[float] = None,
        where: Optional[dict] = None,
        search_terms: Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Semantic search in *collection*.

        Combined score = (1 - w) * cosine_similarity + w * importance_score,
        where w is derived from *query_type* unless *importance_weight* given.

        If *search_terms* are provided (e.g. from AI query analysis) they are
        used for the keyword-boost step instead of tokenising the raw query.
        """
        w = importance_weight if importance_weight is not None else \
            self.IMPORTANCE_WEIGHTS.get(query_type, 0.15)

        if self.using_chromadb and self.client:
            return self._search_chromadb(collection, query, top_k, w, where, search_terms)
        return self._search_memory(collection, query, top_k, w, search_terms)

    # ------------------------------------------------------------------
    # Public API — collection info
    # ------------------------------------------------------------------

    def collection_exists(self, collection: str) -> bool:
        if self.using_chromadb and self.client:
            try:
                return self.client.get_collection(collection).count() > 0
            except Exception:
                pass
        return bool(self._memory.get(collection, {}).get('documents'))

    def collection_count(self, collection: str) -> int:
        if self.using_chromadb and self.client:
            try:
                return self.client.get_collection(collection).count()
            except Exception:
                pass
        return len(self._memory.get(collection, {}).get('documents', []))

    # ------------------------------------------------------------------
    # Public API — chunking helpers
    # ------------------------------------------------------------------

    def chunk_sliding(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> List[str]:
        """Split *text* into overlapping windows, always at word boundaries."""
        text = (text or '').strip()
        if not text:
            return ['']
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)

            # Snap end backward to a sentence or word boundary
            if end < text_len:
                end = self._snap_end(text, start, end)

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_len:
                break

            # Overlap: back up, then snap forward to word boundary
            next_start = max(start + 1, end - overlap)
            next_start = self._snap_start(text, next_start, text_len)

            # Guarantee forward progress
            if next_start <= start:
                next_start = end

            start = next_start

        return chunks or [text]

    @staticmethod
    def _snap_end(text: str, start: int, end: int) -> int:
        """Snap *end* backward to nearest sentence or word boundary."""
        min_pos = start + (end - start) // 2
        # Prefer last sentence-ending punctuation (.!? followed by space/end)
        best = -1
        for m in re.finditer(r'[.!?](?:\s|$)', text[start:end]):
            pos = start + m.start() + 1  # include the punctuation char
            if pos >= min_pos:
                best = pos
        if best > 0:
            return best
        # Fall back to last whitespace
        space = text.rfind(' ', min_pos, end)
        return space if space > start else end

    @staticmethod
    def _snap_start(text: str, pos: int, text_len: int) -> int:
        """If *pos* is mid-word, advance to the start of the next word."""
        if pos <= 0 or pos >= text_len:
            return pos
        # Already at a word start (previous char is whitespace)
        if text[pos - 1].isspace():
            return pos
        # Mid-word — skip past current word, then past whitespace
        while pos < text_len and not text[pos].isspace():
            pos += 1
        while pos < text_len and text[pos].isspace():
            pos += 1
        return pos

    def chunk_semantic(
        self,
        text: str,
        max_chunk_size: int = 1000,
        similarity_threshold: float = 0.45,
    ) -> List[str]:
        """
        Split *text* at topic-boundary breaks detected by cosine-similarity drops.

        Falls back to :meth:`chunk_sliding` if encoding fails or text is short.
        """
        if not text or not text.strip():
            return [text] if text else ['']
        if len(text) <= max_chunk_size:
            return [text]

        # Minimum useful chunk size — never flush below this
        min_chunk_size = max(200, max_chunk_size // 5)

        # Build segments: merge single newlines (PDF lines), split only
        # at real paragraph breaks (double newline) or sentence boundaries
        # in long blocks.
        segments = []
        for para in re.split(r'\n{2,}', text.strip()):
            para = para.strip()
            if not para:
                continue
            # Re-join single-newline line breaks inside a paragraph
            para = re.sub(r'(?<!\n)\n(?!\n)', ' ', para)
            if len(para) < 300:
                segments.append(para)
            else:
                # Split at sentence boundaries only (not bare newlines)
                for seg in re.split(r'(?<=[.!?])\s+', para):
                    seg = seg.strip()
                    if seg and len(seg) > 10:
                        segments.append(seg)
        segments = [s for s in segments if s and len(s.strip()) > 10]

        if len(segments) <= 1:
            return self.chunk_sliding(text, chunk_size=max_chunk_size, overlap=200)

        try:
            vecs = self.embedding_model.encode(segments)
        except Exception as e:
            logger.warning(f"[chunk_semantic] encode failed: {e}, fallback to sliding")
            return self.chunk_sliding(text, chunk_size=max_chunk_size, overlap=200)

        # Find breakpoints where topic changes (similarity drops below threshold)
        breakpoints = set()
        for i in range(len(vecs) - 1):
            a, b = vecs[i], vecs[i + 1]
            sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
            if sim < similarity_threshold:
                breakpoints.add(i + 1)

        # Group segments into chunks.
        # Only flush at breakpoints when the chunk has reached min_chunk_size.
        chunks, buf, buf_len = [], [], 0
        for i, seg in enumerate(segments):
            # If a single segment exceeds max, sub-split it at sentence/word boundaries
            if len(seg) > max_chunk_size:
                # Flush whatever is in the buffer first
                if buf:
                    chunks.append('\n'.join(buf))
                    buf, buf_len = [], 0
                # Sub-split the oversized segment
                for sub in self.chunk_sliding(seg, chunk_size=max_chunk_size, overlap=100):
                    chunks.append(sub)
                continue

            # Hard limit: flush if adding this segment exceeds max_chunk_size
            if buf_len + len(seg) > max_chunk_size and buf:
                chunks.append('\n'.join(buf))
                buf, buf_len = [], 0
            buf.append(seg)
            buf_len += len(seg) + 1
            # Only flush at topic breakpoint if chunk is large enough
            if i in breakpoints and buf_len >= min_chunk_size:
                chunks.append('\n'.join(buf))
                buf, buf_len = [], 0
        if buf:
            chunks.append('\n'.join(buf))

        return chunks or [text]

    # ------------------------------------------------------------------
    # Public encoding helper
    # ------------------------------------------------------------------

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode a list of texts and return embedding vectors."""
        return self._encode(texts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encode(self, texts: List[str]) -> List[List[float]]:
        return [v.tolist() for v in self.embedding_model.encode(texts)]

    def _search_chromadb(
        self,
        collection: str,
        query: str,
        top_k: int,
        w: float,
        where: Optional[dict],
        search_terms: Optional[List[str]] = None,
    ) -> List[dict]:
        try:
            col = self.client.get_collection(collection)
            total = col.count()
            if total == 0:
                return []
            fetch_k = min(total, max(top_k * 3, 15))
            qvec = self.embedding_model.encode(query).tolist()
            kwargs: dict = dict(
                query_embeddings=[qvec],
                n_results=fetch_k,
                include=["documents", "metadatas", "distances"],
            )
            if where:
                kwargs["where"] = where
            res = col.query(**kwargs)
            candidates = []
            if res['documents'] and res['documents'][0]:
                for doc, meta, dist in zip(
                    res['documents'][0],
                    res['metadatas'][0],
                    res['distances'][0],
                ):
                    sim = max(0.0, 1.0 - dist / 2.0)
                    imp = self._importance_from_meta(meta)
                    kw = self._keyword_boost(query, doc, search_terms)
                    combined = (1 - w) * sim + w * imp + kw
                    candidates.append({
                        'content': doc,
                        'metadata': meta,
                        'relevance_score': sim,
                        'importance_score': imp,
                        'keyword_boost': kw,
                        'combined_score': combined,
                    })
            candidates.sort(key=lambda x: x['combined_score'], reverse=True)
            return candidates[:top_k]
        except Exception as e:
            logger.error(f"[VectorStore] ChromaDB search error '{collection}': {e}", exc_info=True)
            return []

    def _search_memory(
        self,
        collection: str,
        query: str,
        top_k: int,
        w: float,
        search_terms: Optional[List[str]] = None,
    ) -> List[dict]:
        col = self._memory.get(collection)
        if not col or not col.get('documents'):
            return []
        qvec = self.embedding_model.encode(query)
        scored = []
        for doc, meta, vec in zip(col['documents'], col['metadatas'], col['embeddings']):
            ev = np.array(vec)
            sim = float(np.dot(qvec, ev) / (np.linalg.norm(qvec) * np.linalg.norm(ev) + 1e-10))
            imp = self._importance_from_meta(meta)
            kw = self._keyword_boost(query, doc, search_terms)
            combined = (1 - w) * sim + w * imp + kw
            scored.append({
                'content': doc,
                'metadata': meta,
                'relevance_score': sim,
                'importance_score': imp,
                'keyword_boost': kw,
                'combined_score': combined,
            })
        scored.sort(key=lambda x: x['combined_score'], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _importance_from_meta(meta: dict) -> float:
        try:
            return float(meta.get('importance_score', 0.5))
        except (ValueError, TypeError):
            return 0.5

    @staticmethod
    def _keyword_boost(
        query: str,
        document: str,
        search_terms: 'Optional[List[str]]' = None,
    ) -> float:
        """Lexical boost: reward chunks that contain query keywords.

        Returns a value in [0.0, 0.30].  A chunk that contains ALL
        important query terms gets the full 0.30 boost; partial matches
        get a proportional fraction.  Stop-words are ignored.

        If *search_terms* are provided (e.g. AI-extracted concepts) they
        are used instead of tokenising the raw query.
        """
        doc_lower = document.lower()

        if search_terms:
            hits = sum(1 for t in search_terms if t.lower() in doc_lower)
            return 0.30 * (hits / len(search_terms))

        _STOP = {
            'a', 'al', 'con', 'de', 'del', 'el', 'en', 'es', 'la', 'las',
            'lo', 'los', 'o', 'para', 'por', 'que', 'se', 'son', 'su', 'un',
            'una', 'y', 'the', 'is', 'of', 'and', 'in', 'to', 'a', 'an',
            'it', 'for', 'on', 'are', 'was', 'what', 'how', 'which', 'who',
            'me', 'dame', 'dime', 'can', 'do', 'this', 'that',
        }
        q_words = [
            w for w in re.findall(r'\b[\w]{2,}\b', query.lower())
            if w not in _STOP
        ]
        if not q_words:
            return 0.0
        hits = sum(1 for w in q_words if w in doc_lower)
        return 0.30 * (hits / len(q_words))

    def _load_json_store(self) -> None:
        for p in Path(self.json_dir).glob('*.json'):
            try:
                with open(p, encoding='utf-8') as f:
                    self._memory[p.stem] = json.load(f)
            except Exception as e:
                logger.warning(f"[VectorStore] could not load {p.name}: {e}")

    def _save_json_store(self, collection: str) -> None:
        p = Path(self.json_dir) / f"{collection}.json"
        try:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(self._memory[collection], f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[VectorStore] could not save {collection}: {e}")


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_instance: Optional[VectorStore] = None


def get_vector_store(
    persist_dir: Optional[str] = None,
    json_dir: Optional[str] = None,
) -> VectorStore:
    """
    Return the shared VectorStore instance (lazy-initialised).

    From a Django context:

        from django.conf import settings
        from tu_app.vector_store import get_vector_store
        import os

        vs = get_vector_store(
            persist_dir=os.path.join(settings.BASE_DIR, '.chroma_db'),
            json_dir=os.path.join(settings.BASE_DIR, '.embeddings'),
        )
    """
    global _instance
    if _instance is None:
        _instance = VectorStore(persist_dir=persist_dir, json_dir=json_dir)
    return _instance
