import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout, redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from book_distiller.__main__ import main
from book_distiller.provider import Provider
from book_distiller.cards import build_card
from book_distiller.evidence import InvalidInput
from book_distiller.io import json_bytes

EXAMPLES = Path(__file__).resolve().parents[1]/'examples'

class FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append((self.path, self.headers.get('Authorization'), body))
        if self.path == '/requires-agent' and not self.headers.get('User-Agent','').startswith('BookDistiller/'):
            self.send_response(403); self.end_headers(); return
        if self.path == '/redirect':
            self.send_response(307); self.send_header('Location', '/target'); self.end_headers(); return
        if self.path == '/fail':
            self.send_response(500); self.end_headers(); self.wfile.write(b'PRIVATE-ERROR-CONTENT'); return
        self.send_response(200); self.end_headers()
        content = 'invalid json' if self.path == '/malformed' else json.dumps(self.server.result, ensure_ascii=False)
        self.wfile.write(json_bytes({'choices':[{'message':{'content':content}}]}))

class NetworkBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),FakeHandler)
        self.server.requests=[]
        self.server.result=json.loads((EXAMPLES/'card-fiction-response.json').read_bytes())
        self.thread=threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.env=patch.dict(os.environ, {'BOOK_DISTILLER_TEST_KEY':'local-test-placeholder'}); self.env.start()
    def tearDown(self):
        self.env.stop(); self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def config(self, path='/ok', **change):
        data={'endpoint':f'http://127.0.0.1:{self.server.server_port}{path}', 'model':'test-model', 'api_key_env':'BOOK_DISTILLER_TEST_KEY'}
        data.update(change); p=self.root/'config.json'; p.write_bytes(json_bytes(data)); return p
    def test_explicit_online_cli_and_role_separation(self):
        out=self.root/'card'
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            code=main(['card', str(EXAMPLES/'card-fiction-input.json'), '--online','--config',str(self.config()),'--out',str(out)])
        self.assertEqual(code,0); self.assertTrue((out/'card.md').is_file())
        request=self.server.requests[0][2]
        self.assertEqual([m['role'] for m in request['messages']],['system','user'])
        self.assertIn('highlights',json.loads(request['messages'][1]['content']))
        self.assertNotIn('local-test-placeholder', (out/'references.json').read_text(encoding='utf-8'))
    def test_redirect_not_followed_or_authorization_forwarded(self):
        with self.assertRaises(InvalidInput):
            Provider(self.config('/redirect')).complete('instruction',{})
        self.assertEqual([r[0] for r in self.server.requests],['/redirect'])
    def test_http_error_body_never_echoed(self):
        with self.assertRaises(InvalidInput) as error:
            Provider(self.config('/fail')).complete('instruction',{})
        self.assertIn('500',str(error.exception)); self.assertNotIn('PRIVATE-ERROR', str(error.exception))
    def test_malformed_model_json_no_formal_output(self):
        out=self.root/'card'; err=io.StringIO()
        with redirect_stdout(io.StringIO()),redirect_stderr(err):
            code=main(['card',str(EXAMPLES/'card-fiction-input.json'),'--online','--config',str(self.config('/malformed')),'--out',str(out)])
        self.assertEqual(code,2); self.assertFalse(out.exists())
    def test_cached_response_rechecked_and_request_hash_changes(self):
        cache=self.root/'cache'; config=self.config(); p=Provider(config,cache)
        data=json.loads((EXAMPLES/'card-fiction-input.json').read_bytes())
        result=p.complete('instruction',data); self.assertEqual(p.complete('instruction',data),result)
        self.assertEqual(len(self.server.requests),1)
        path=next(cache.glob('*.json')); result['golden_quotes']=['伪造。〔划线1〕']; path.write_bytes(json_bytes(result))
        with self.assertRaises(InvalidInput):
            build_card(data,p.complete('instruction',data),'x','llm')
        p.complete('changed instruction',data)
        self.assertEqual(len(self.server.requests),2); self.assertEqual(len(list(cache.glob('*.json'))),2)
        self.assertNotIn('local-test-placeholder', ''.join(f.read_text(encoding='utf-8') for f in cache.glob('*.json')))
    def test_missing_key_before_request(self):
        config=self.config(api_key_env='BOOK_DISTILLER_ABSENT_TEST_KEY')
        with patch.dict(os.environ,{},clear=True),self.assertRaises(InvalidInput):
            Provider(config).complete('x',{})
        self.assertEqual(self.server.requests,[])
    def test_inline_key_and_remote_http_refused(self):
        with self.assertRaises(InvalidInput):
            Provider(self.config(api_key='unsafe-test-value'))
        with self.assertRaises(InvalidInput):
            Provider(self.config(endpoint='http://provider.example/completions'))
        self.assertEqual(self.server.requests,[])
    def test_non_string_endpoint_is_input_error(self):
        for endpoint in (42, [], None):
            with self.subTest(endpoint=endpoint),self.assertRaises(InvalidInput):
                Provider(self.config(endpoint=endpoint))
        self.assertEqual(self.server.requests,[])
    def test_identified_application_accepted_by_agent_filter(self):
        out=self.root/'card';err=io.StringIO()
        with redirect_stdout(io.StringIO()),redirect_stderr(err):
            code=main(['card',str(EXAMPLES/'card-fiction-input.json'),'--online','--config',str(self.config('/requires-agent')),'--out',str(out)])
        self.assertEqual(code,0,err.getvalue())
        self.assertTrue((out/'card.json').exists())

if __name__ == '__main__':
    unittest.main()
