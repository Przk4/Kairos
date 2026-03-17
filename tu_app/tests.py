from unittest import mock

from django.test import SimpleTestCase

from tu_app.question_preprocessor import QuestionPreprocessor
from tu_app.query_analyzer import QueryAnalyzer


class QuestionPreprocessorTests(SimpleTestCase):
	def test_preserves_text_inside_quotes(self):
		preprocessor = QuestionPreprocessor()

		with mock.patch.object(preprocessor, '_get_tool', return_value=object()), \
			 mock.patch.object(preprocessor, '_correct_segment', side_effect=lambda text, tool: text.replace('ortografia', 'ortografía')):
			result = preprocessor.preprocess('corrije ortografia de "teh exact term" porfa')

		self.assertIn('ortografía', result['interpreted_question'])
		self.assertIn('"teh exact term"', result['interpreted_question'])
		self.assertTrue(result['correction_applied'])


class QueryAnalyzerTests(SimpleTestCase):
	def test_extracts_quoted_terms_and_classifies_summary(self):
		analyzer = QueryAnalyzer()

		result = analyzer.analyze('haz un resumen de "critical path" y sus fases')

		self.assertEqual(result['query_type'], 'summary')
		self.assertIn('critical path', result['search_terms'])
