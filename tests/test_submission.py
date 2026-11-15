import asyncio
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

_scratch = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(_scratch.name)/'test.db').as_posix()

from fastapi.testclient import TestClient
from app.main import app
from app.api import routes_search
from app.api.workflow import run_workflow
from app.config import settings
from app.retrieval.hybrid_search import build_filter_expr
from app.retrieval.store import engine

retrieval = importlib.import_module('app.agents.nodes.retrieve')
grading = importlib.import_module('app.agents.nodes.grade_evidence')


def tearDownModule():
    engine.dispose()
    _scratch.cleanup()


class SubmissionChecks(unittest.TestCase):
    def test_single_origin_ui_and_api(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/health').json(), {'status': 'ok'})
            self.assertIn('config.js', client.get('/').text)
            self.assertIn('FLAME_SAME_ORIGIN', client.get('/api-config.js').text)
            self.assertEqual(client.get('/docs').status_code, 200)

    def test_filters_normalize_string_ids_and_escape_quotes(self):
        self.assertEqual(build_filter_expr({'investigation_id': 'BASS-II'}), 'investigation_id in ["BASS-II"]')
        value = 'cotton" or material != "'
        self.assertEqual(build_filter_expr({'material': value}), 'material == ' + json.dumps(value))

    def test_empty_filtered_search_keeps_restriction(self):
        with patch.object(retrieval, 'hybrid_search', return_value=[]) as search:
            result = retrieval.retrieve({'question':'Only BASS-II', 'filters':{'investigation_id':['BASS-II']}})
            self.assertEqual(search.call_count, 1)
            self.assertEqual(result['passages'], [])

    def test_malformed_grading_does_not_authorize_generation(self):
        model = SimpleNamespace(invoke=lambda _: SimpleNamespace(content='malformed grading output'))
        with patch.object(grading, 'get_small_llm', return_value=model):
            state = grading.grade_evidence({'question':'test', 'passages':[{'evidence_id':'P1','text':'fixture', 'retrieval_score':1.0}]})
            self.assertEqual(state['evidence_grade'], 'insufficient')

    def test_dependency_failure_returns_safe_502(self):
        async def fail(_):
            raise RuntimeError('private dependency details')
        with TestClient(app) as client, patch.object(routes_search.compiled_graph, 'ainvoke', side_effect=fail):
            response = client.post('/api/search', json={'question':'test'})
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('private dependency', response.text)

    def test_timeout_returns_504(self):
        async def slow(_):
            await asyncio.sleep(1)
        from fastapi import HTTPException
        with patch.object(settings, 'workflow_timeout_seconds', 0.001):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(run_workflow(SimpleNamespace(ainvoke=slow), {}))
        self.assertEqual(error.exception.status_code, 504)

    def test_search_response_contract(self):
        async def result(_):
            return {'answer':'Fixture response', 'evidence_status':'insufficient', 'passages':[], 'citations':[], 'ranked_investigations':[]}
        with TestClient(app) as client, patch.object(routes_search.compiled_graph, 'ainvoke', side_effect=result):
            response = client.post('/api/search', json={'question':'test'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['evidence_status'], 'insufficient')

    def test_empty_question_is_rejected(self):
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/search', json={'question':'  '}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
