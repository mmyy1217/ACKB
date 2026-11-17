import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import site_build
from insights import render as render_insights


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = {'version': 'test', 'records': [{'id': 'raw', 'name': 'copy', 'parameters': ['ptr', 'count']}], 'files': [{'path': 'header.h', 'sha256': 'evidence'}]}
        self.knowledge = {'ccec': {'topics': [], 'ops': {'ops': [{'id': 'builtin', 'builtin': '__builtin_copy', 'forms': [1, 2]}]}},
                          'ptx': {'records': [{'id': 'add', 'signature': 'add.s32'}]},
                          'ascendc': {'basic_api': [], 'c_api': []}, 'cce_dialect': {'ops': [], 'intrinsics': []},
                          'llvm': {'ops': {'columns': ['id', 'name'], 'rows': [['llvm_ir_copy', 'llvm.hivm.copy']]}, 'forms': ['type evidence'], 'relations': [{'from': 'builtin', 'to': 'llvm_ir_copy'}]}}

    def build(self, style='css', script='js', title=None):
        template = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text()
        template = template.replace('<!--__ASCENDC_MAP__-->', (Path(__file__).resolve().parents[1] / 'web/ascendc-map.html').read_text())
        template = template.replace('<!--__INSIGHTS__-->', render_insights())
        if title:
            template = template.replace('AI Compiler 目标知识库', title)
        with redirect_stdout(StringIO()):
            site_build.build_site(template, style, script, self.data, self.knowledge, self.root / 'index.html')
        return json.loads((self.root / 'manifest.json').read_text())

    def test_split_snapshots_are_lossless_and_content_verified(self):
        manifest = self.build()
        expected = {'ccec': {'catalog': self.data, 'knowledge': self.knowledge['ccec']},
                    'navigation': site_build.navigation_data(self.data, self.knowledge),
                    **{name: self.knowledge[key] for name, key in [('ptx', 'ptx'), ('llvm', 'llvm'), ('ascendc', 'ascendc'), ('cce-dialect', 'cce_dialect')]}}
        expected['nvvm'] = {}
        for name, pair in manifest['datasets'].items():
            raw = (self.root / pair['plain']['url']).read_bytes()
            self.assertEqual(gzip.decompress((self.root / pair['gzip']['url']).read_bytes()), raw)
            self.assertEqual(json.loads(raw), {'schema': site_build.SCHEMA, 'dataset': name, 'payload': expected[name]})
            for item in pair.values():
                content = (self.root / item['url']).read_bytes()
                self.assertEqual(item['sha256'], hashlib.sha256(content).hexdigest())
                self.assertEqual(item['bytes'], len(content))
        html = (self.root / 'index.html').read_text()
        self.assertNotIn('__builtin_copy', html)
        self.assertNotIn('/*__', html)
        self.assertIn('<main id="home" aria', html)

    def test_rebuild_reuses_all_asset_names(self):
        self.assertEqual(self.build(), self.build())

    def test_instruction_update_only_invalidates_affected_data(self):
        before = self.build()
        self.knowledge['llvm']['forms'].append('new signature')
        after = self.build()
        self.assertNotEqual(before['revision'], after['revision'])
        for name in before['datasets']:
            if name == 'llvm':
                self.assertNotEqual(before['datasets'][name], after['datasets'][name])
            else:
                self.assertEqual(before['datasets'][name], after['datasets'][name])
        self.assertEqual(before['script'], after['script'])
        self.assertEqual(before['style'], after['style'])

    def test_new_instruction_updates_routing_without_stale_assets(self):
        before = self.build()
        self.knowledge['llvm']['ops']['rows'].append(['llvm_ir_new', 'llvm.hivm.new'])
        after = self.build()
        self.assertNotEqual(before['datasets']['navigation'], after['datasets']['navigation'])
        self.assertFalse((self.root / before['datasets']['llvm']['gzip']['url']).exists())
        self.assertTrue((self.root / after['datasets']['llvm']['gzip']['url']).exists())

    def test_ui_update_keeps_database_cache(self):
        before = self.build()
        after = self.build(style='new css', script='new js')
        self.assertEqual(before['datasets'], after['datasets'])
        self.assertNotEqual(before['script'], after['script'])
        self.assertNotEqual(before['style'], after['style'])
        self.assertNotEqual(before['revision'], after['revision'])

    def test_html_only_update_is_detectable(self):
        before = self.build()
        after = self.build(title='新的首页')
        self.assertEqual(before['datasets'], after['datasets'])
        self.assertEqual(before['script'], after['script'])
        self.assertEqual(before['style'], after['style'])
        self.assertNotEqual(before['revision'], after['revision'])


if __name__ == '__main__':
    unittest.main()
