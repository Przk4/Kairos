import logging
import re
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)

_DOUBLE_QUOTE_RE = re.compile(r'"([^"\n]*)"|“([^”\n]*)”')
_PLACEHOLDER_RE = re.compile(r'__KAIROS_QUOTED_(\d+)__')


class QuestionPreprocessor:
    def __init__(self):
        self._tool = None
        self._tool_failed = False

    def _get_tool(self):
        if self._tool_failed:
            return None
        if self._tool is not None:
            return self._tool
        try:
            import language_tool_python
            self._tool = language_tool_python.LanguageTool('es')
        except Exception as exc:
            self._tool_failed = True
            logger.warning("QuestionPreprocessor: LanguageTool unavailable: %s", exc)
            return None
        return self._tool

    def _protect_quoted_segments(self, text: str) -> Tuple[str, List[str]]:
        literals: List[str] = []

        def _replace(match: re.Match) -> str:
            literal = match.group(0)
            literals.append(literal)
            return f'__KAIROS_QUOTED_{len(literals) - 1}__'

        protected = _DOUBLE_QUOTE_RE.sub(_replace, text)
        return protected, literals

    def _restore_quoted_segments(self, text: str, literals: List[str]) -> str:
        def _replace(match: re.Match) -> str:
            index = int(match.group(1))
            return literals[index] if 0 <= index < len(literals) else match.group(0)

        return _PLACEHOLDER_RE.sub(_replace, text)

    def _correct_segment(self, segment: str, tool) -> str:
        if not segment.strip() or tool is None:
            return segment
        try:
            matches = tool.check(segment)
            if not matches:
                return segment
            import language_tool_python
            return language_tool_python.utils.correct(segment, matches)
        except Exception as exc:
            logger.warning("QuestionPreprocessor: correction failed: %s", exc)
            return segment

    def _correct_outside_quotes(self, text: str) -> Tuple[str, List[str]]:
        tool = self._get_tool()
        protected_text, literals = self._protect_quoted_segments(text)
        parts = re.split(r'(__KAIROS_QUOTED_\d+__)', protected_text)
        corrected_parts = []
        for part in parts:
            if not part:
                continue
            if _PLACEHOLDER_RE.fullmatch(part):
                corrected_parts.append(part)
            else:
                corrected_parts.append(self._correct_segment(part, tool))
        corrected = ''.join(corrected_parts)
        corrected = self._restore_quoted_segments(corrected, literals)
        return corrected, literals

    def preprocess(self, question: str) -> Dict[str, Any]:
        original = (question or '').strip()
        if not original:
            return {
                'original_question': '',
                'interpreted_question': '',
                'correction_applied': False,
                'quoted_literals': [],
            }

        corrected, literals = self._correct_outside_quotes(original)
        corrected = re.sub(r'\s+', ' ', corrected).strip()
        original_normalized = re.sub(r'\s+', ' ', original).strip()

        return {
            'original_question': original_normalized,
            'interpreted_question': corrected,
            'correction_applied': corrected != original_normalized,
            'quoted_literals': literals,
        }


_question_preprocessor_instance: Optional[QuestionPreprocessor] = None


def get_question_preprocessor() -> QuestionPreprocessor:
    global _question_preprocessor_instance
    if _question_preprocessor_instance is None:
        _question_preprocessor_instance = QuestionPreprocessor()
    return _question_preprocessor_instance