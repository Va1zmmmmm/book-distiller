import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
from book_distiller.__main__ import main
from book_distiller.cards import build_card
from book_distiller.books import book_input, chunks_for, build_book, build_session
from book_distiller.evidence import InvalidInput, exact_spans, sha
from book_distiller.io import json_bytes, write_bundle, checked_read

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
def fixture(name):
    return json.loads((EXAMPLES / name).read_text(encoding='utf-8'))

class Workflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.book = fixture('book-input.json')
        self.responses = fixture('book-response.json')['chunks']
        self.card = fixture('card-method-input.json')
        self.result = fixture('card-method-response.json')
    def tearDown(self):
        self.temp.cleanup()
    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()
    def bundle(self):
        path = self.root / 'book'
        write_bundle(path, build_book(self.book, self.responses, 'original', 'response-import'))
        return path
    def card_bundle(self):
        path = self.root / 'card'
        write_bundle(path, build_card(self.card, self.result, 'original', 'response-import'))
        return path
    def test_fiction_leaves_method_blank(self):
        files = build_card(fixture('card-fiction-input.json'), fixture('card-fiction-response.json'), 'x', 'response-import')
        self.assertNotIn('## 可带走的东西', files['card.md'])
        self.assertIn('未经读者确认', files['card.md'])
        self.assertIn('未解问题', files['card.md'])
    def test_real_steps_preserved_without_duplicate_number(self):
        files = build_card(self.card, self.result, 'x', 'response-import')
        self.assertIn('1. 复述', files['card.md'])
        self.assertNotIn('1. 1.', files['card.md'])
        self.assertEqual(len(json.loads(files['references.json'])['quote_checks']), 1)
    def test_links_visible(self):
        self.result['links'] = ['回信：我的阅读记录中反复关心的问题。']
        self.assertIn('## 关联线索', build_card(self.card, self.result, 'x', 'test')['card.md'])
    def test_wrong_highlight_rejected(self):
        self.result['takeable']['quote'] = self.card['highlights'][0]['text'] + '〔划线2〕'
        with self.assertRaises(InvalidInput):
            build_card(self.card, self.result, 'x', 'test')
    def test_nonexistent_claim_support_rejected(self):
        self.result['claim_sources'][0] = ['h99']
        with self.assertRaises(InvalidInput):
            build_card(self.card, self.result, 'x', 'test')
    def test_steps_need_individual_sources(self):
        self.result.pop('steps_sources')
        with self.assertRaises(InvalidInput):
            build_card(self.card, self.result, 'x', 'test')
    def test_unmarked_join_and_normalized_punctuation_rejected(self):
        self.assertIsNone(exact_spans('甲丙', '甲乙丙'))
        self.assertIsNone(exact_spans('甲,乙', '甲，乙'))
        self.assertEqual([s['start'] for s in exact_spans('甲[……]丙', '甲乙丙')], [0, 2])
    def test_repeated_segments_must_be_sequential(self):
        self.assertIsNone(exact_spans('甲[……]甲', '甲'))
        self.assertEqual([s['start'] for s in exact_spans('甲[……]甲', '甲乙甲')], [0, 2])
    def test_long_chapter_all_characters_preserved(self):
        text = ('首段\n' + '甲' * 17000 + '\n末段尾部' * 4000)
        self.book['chapters'][0]['text'] = text
        parts = [c for c in chunks_for(self.book) if c['chapter_id'] == 'c1']
        self.assertEqual(''.join(c['text'] for c in parts), text)
        self.assertTrue(all(len(c['text']) <= 12000 for c in parts))
        self.assertTrue(all(a['end'] == b['start'] for a,b in zip(parts, parts[1:])))
    def test_source_only_preparation(self):
        files = build_book(self.book, None, 'x', 'source-only')
        self.assertEqual(files['chapters/c3.md'].decode('utf-8'), self.book['chapters'][2]['text'])
        self.assertEqual(json.loads(files['quotes.json']), [])
        self.assertNotIn('analysis/c1-001.json', files)
    def test_stale_chunk_set_rejected(self):
        self.responses['old-001'] = self.responses.pop('c1-001')
        with self.assertRaises(InvalidInput):
            build_book(self.book, self.responses, 'x', 'test')
    def test_quote_in_wrong_chapter_rejected(self):
        self.responses['c1-001']['quotes'] = self.responses['c3-001']['quotes']
        with self.assertRaises(InvalidInput):
            build_book(self.book, self.responses, 'x', 'test')
    def test_quote_in_other_chunk_same_chapter_rejected(self):
        self.book['chapters'] = [{'id':'c1', 'title':'章', 'text':'甲' * 12000 + '仅在尾部。'}]
        responses = {'c1-001': {'summary':'前部','concepts':[], 'quotes':['仅在尾部。']}, 'c1-002': {'summary':'尾部','concepts':[], 'quotes':[]}}
        with self.assertRaises(InvalidInput):
            build_book(self.book, responses, 'x', 'test')
    def test_no_future_title_text_analysis_quote_or_note(self):
        root = self.bundle()
        notes = root / 'notes'; notes.mkdir()
        (notes / 'future.json').write_bytes(json_bytes({'chapter_id':'c3', 'reader':'青灯晚潮'}))
        files = build_session(root, 'c1')
        visible = '\n'.join(v.decode('utf-8') if isinstance(v,bytes) else v for v in files.values())
        for forbidden in ['青灯晚潮','桥的另一端','寄不出的明信片','c2-001','c3-001']:
            self.assertNotIn(forbidden, visible)
        self.assertNotIn('manifest.json', files)
        self.assertNotIn('chapters/c2.md', files)
    def test_partial_chapter_excludes_later_lines_analysis_notes(self):
        root = self.bundle()
        notes = root / 'notes'; notes.mkdir()
        (notes / 'current.json').write_bytes(json_bytes({'chapter_id':'c1', 'reader':'私有整章猜测'}))
        files = build_session(root, 'c1', 2)
        self.assertEqual(files['chapters/c1.md'].decode(), ''.join(self.book['chapters'][0]['text'].splitlines(keepends=True)[:2]))
        self.assertNotIn('analysis/c1-001.json', files)
        self.assertEqual(json.loads(files['quotes.json']), [])
        self.assertEqual(json.loads(files['notes.json']), [])
    def test_changed_source_analysis_and_quotes_all_block(self):
        for name in ('chapters/c1.md','analysis/c1-001.json','quotes.json'):
            with self.subTest(name=name):
                root = self.root / name.replace('/', '-')
                write_bundle(root, build_book(self.book, self.responses, 'x','test'))
                (root / name).write_bytes(b'tampered')
                with self.assertRaises(InvalidInput):
                    build_session(root, 'c1')
    def test_path_escape_and_chapter_ids_rejected(self):
        with self.assertRaises(InvalidInput):
            checked_read(self.root, '../elsewhere', 'x')
        self.book['chapters'][0]['id'] = '../oops'
        with self.assertRaises(InvalidInput):
            book_input(self.book)
    def test_windows_device_name_rejected_before_output(self):
        self.book['chapters'][0]['id'] = 'CON'
        with self.assertRaises(InvalidInput):
            build_book(self.book, None, 'x', 'test')
    def test_unicode_separator_uses_same_lf_coordinates(self):
        self.book['chapters'] = [{'id':'c1','title':'章','text':'第一行\u2028同一行\r\n第二行\n后段。'}]
        response={'c1-001': {'summary':'演示','concepts':[],'quotes':['后段。']}}
        root=self.root/'lf-book'; write_bundle(root, build_book(self.book,response,'x','test'))
        files=build_session(root,'c1',1)
        self.assertEqual(files['chapters/c1.md'].decode(), '第一行\u2028同一行\r\n')
        self.assertEqual(json.loads(files['quotes.json']), [])
    def test_through_final_line_keeps_complete_chapter_notes(self):
        root=self.bundle(); self.cli('note',root,'--event',EXAMPLES/'note-event.json')
        files=build_session(root,'c1',4)
        self.assertIn('analysis/c1-001.json',files)
        self.assertEqual(len(json.loads(files['notes.json'])),1)
    def test_duplicate_chapter_ids_rejected(self):
        self.book['chapters'][1]['id'] = 'c1'
        with self.assertRaises(InvalidInput):
            book_input(self.book)
    def test_empty_material_and_partial_range_fail(self):
        with self.assertRaises(InvalidInput):
            build_card({'book':{'title':'空'}}, self.result, 'x', 'test')
        root = self.bundle()
        for n in (0, 999):
            with self.assertRaises(InvalidInput):
                build_session(root, 'c1', n)
    def test_existing_output_stops_before_model_call(self):
        root = self.root / 'existing'; root.mkdir()
        (root / 'manual.txt').write_bytes(b'manual')
        with patch('book_distiller.__main__.Provider') as provider:
            code, _, _ = self.cli('card', EXAMPLES/'card-method-input.json', '--online', '--config','not-read.json','--out', root)
        self.assertEqual(code, 2)
        provider.assert_not_called()
        self.assertEqual((root/'manual.txt').read_bytes(), b'manual')
    def test_invalid_response_creates_no_formal_output(self):
        response = self.root/'bad.json'; self.result['golden_quotes'] = ['编造内容。〔划线1〕']
        response.write_bytes(json_bytes(self.result))
        target = self.root/'not-created'
        self.assertEqual(self.cli('card', EXAMPLES/'card-method-input.json', '--response',response,'--out', target)[0], 2)
        self.assertFalse(target.exists())
    def test_note_roles_preserved_and_append_only(self):
        root = self.bundle()
        for _ in range(2):
            self.assertEqual(self.cli('note',root,'--event',EXAMPLES/'note-event.json')[0], 0)
        paths = list((root/'notes').glob('*.json'))
        self.assertEqual(len(paths), 2)
        events = json.loads(build_session(root,'c1')['notes.json'])
        self.assertEqual(events[0]['reader'], fixture('note-event.json')['reader'])
        self.assertNotEqual(events[0]['reader'], events[0]['ai'])
        self.assertEqual([e['recorded_at'] for e in events], sorted(e['recorded_at'] for e in events))
    def test_partial_acceptance_and_candidate_unchanged(self):
        root = self.card_bundle(); before = (root/'card.json').read_bytes()
        self.assertEqual(self.cli('review',root,'--decision','partial','--accept-claim','1')[0], 0)
        event = json.loads(next((root/'reviews').glob('*.json')).read_bytes())
        self.assertEqual(event['accepted_claims'], [1]); self.assertFalse(event['accept_takeable'])
        self.assertEqual((root/'card.json').read_bytes(), before)
    def test_full_acceptance_records_all_and_reject_records_none(self):
        root = self.card_bundle()
        self.assertEqual(self.cli('review',root,'--decision','accept')[0], 0)
        self.assertEqual(self.cli('review',root,'--decision','reject')[0], 0)
        events = [json.loads(p.read_bytes()) for p in (root/'reviews').glob('*.json')]
        accepted = next(e for e in events if e['decision']=='accept')
        rejected = next(e for e in events if e['decision']=='reject')
        self.assertEqual(accepted['accepted_claims'], [1,2]); self.assertTrue(accepted['accept_takeable'])
        self.assertEqual(rejected['accepted_claims'], []); self.assertFalse(rejected['accept_takeable'])
    def test_review_refuses_tampered_candidate(self):
        root = self.card_bundle()
        (root/'card.json').write_bytes(json_bytes({'core_claims':['altered']}))
        self.assertEqual(self.cli('review',root,'--decision','accept')[0], 2)
        self.assertFalse((root/'reviews').exists())
    def test_online_flags_cannot_silently_network(self):
        code, _, _ = self.cli('prepare', EXAMPLES/'book-input.json', '--config','x', '--out',self.root/'unused')
        self.assertEqual(code, 2)
        self.assertFalse((self.root/'unused').exists())

if __name__ == '__main__':
    unittest.main()
