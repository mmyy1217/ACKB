import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from database import Database, identities


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database()

    def test_identity_survives_version_line_and_condition_changes(self):
        original = self.db.records[0]
        moved = copy.deepcopy(original)
        moved.update(id='other', conditions=['OTHER'], source={'file': 'renamed.h', 'line': 999}, version='next')
        self.assertEqual(identities(original), identities(moved))
        moved['signature'] += ' extra_parameter'
        self.assertEqual(identities(original)[0], identities(moved)[0])
        self.assertNotEqual(identities(original)[1], identities(moved)[1])
        moved['namespace'] = 'other'
        self.assertNotEqual(identities(original)[0], identities(moved)[0])

    def test_whitespace_does_not_change_variant(self):
        record = copy.deepcopy(self.db.records[0])
        expected = identities(record)
        record['signature'] = record['signature'].replace(' ', '\n  ')
        self.assertEqual(expected, identities(record))

    def test_variant_keeps_every_source_occurrence(self):
        variant = next(k for k, rows in self.db.by_variant.items() if len(rows) > 1)
        rows = self.db.select(identity=variant, kind='all')
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in self.db.by_variant[variant]})

    def test_unknown_core_never_turns_into_support(self):
        target = self.db.target(chip='Ascend950PR_9579', core='dav-c310-vec')
        self.assertEqual(target['core_evaluation'], 'unverified')
        self.assertEqual(target['profile']['macros'], {'__NPU_ARCH__': 3510})
        with self.assertRaisesRegex(ValueError, 'Core requires'):
            self.db.target(chip='Ascend950PR_9579', core='invented-core')
        with self.assertRaisesRegex(ValueError, 'Unknown chip'):
            self.db.target(chip='made-up')

    def test_builtin_reverse_lookup_has_source_evidence(self):
        builtin = '__builtin_cce_abs_bf16x2'
        rows = self.db.select(builtin=builtin)
        self.assertTrue(rows)
        for r in rows:
            edge = next(e for e in self.db.relations(r) if e.get('target_name') == builtin)
            self.assertEqual(edge['resolution'], 'header_reference')
            self.assertEqual(edge['evidence']['record_id'], r['id'])
            self.assertEqual(len(edge['evidence']['sha256']), 64)

    def test_condition_matches_web_analysis(self):
        target = self.db.target(architecture='__CCE_AICORE__=220')
        record = copy.deepcopy(self.db.records[0])
        record['compatibility']['conditions'] = ['__CCE_AICORE__ == 310']
        self.assertEqual(self.db.condition(record, target), 'excluded')
        record['compatibility']['conditions'] = ['__CCE_AICORE__ == 220 && OTHER']
        self.assertEqual(self.db.condition(record, target), 'unknown')

    def cli(self, *args):
        process = subprocess.run([sys.executable, str(ROOT / 'scripts/query.py'), *args], text=True, capture_output=True)
        self.assertEqual(process.stderr, '')
        return process.returncode, json.loads(process.stdout), process.stdout

    def test_cli_pagination_and_exact_lookup(self):
        code, first, text = self.cli('--limit', '1', 'search', '--name', 'copy_gm_to_cbuf')
        self.assertEqual(code, 0)
        self.assertEqual(len(first['items']), 1)
        self.assertEqual(first['next_offset'], 1)
        self.assertLessEqual(len(text), 24000)
        code, second, _ = self.cli('--limit', '1', '--offset', '1', 'search', '--name', 'copy_gm_to_cbuf')
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        code, detail, _ = self.cli('get', first['items'][0]['id'])
        self.assertEqual(detail['items'][0]['experiments'], [])
        self.assertEqual(detail['items'][0]['semantics']['status'], 'unreviewed')
        code, evidence, _ = self.cli('evidence', first['items'][0]['id'])
        self.assertIn('text', evidence['items'][0])
        self.assertEqual(evidence['items'][0]['representation'], 'original_source_excerpt')

    def test_cli_empty_and_invalid_inputs_are_distinct(self):
        code, result, _ = self.cli('search', '--name', 'no_such_cce_function_xyz')
        self.assertEqual(code, 0)
        self.assertEqual(result['total'], 0)
        self.assertIsNone(result['next_offset'])
        code, error, _ = self.cli('search', '--condition', 'matches')
        self.assertEqual(code, 2)
        self.assertIn('requires', error['error']['message'])
        code, error, _ = self.cli('--limit', '1000', 'search')
        self.assertEqual(code, 2)
        self.assertIn('error', error)

    def test_budget_and_macro_provenance(self):
        for record in self.db.records:
            for evidence in self.db.macro_evidence(record):
                self.assertEqual(len(evidence['sha256']), 64)
                self.assertIn(evidence['file'], self.db.files)
        code, response, text = self.cli('--limit', '50', '--max-chars', '4000', 'search')
        self.assertEqual(code, 0)
        self.assertLessEqual(len(text), 4000)
        self.assertTrue(response['truncated'])
        self.assertGreater(response['next_offset'], 0)
        self.assertEqual(len(response['provenance']['catalog_sha256']), 64)

    def test_json_schema_local_references_exist(self):
        schema = json.loads((ROOT / 'schemas/query-v1.schema.json').read_text())
        def check(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    target = schema
                    for part in value['$ref'][2:].split('/'):
                        target = target[part]
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        check(schema)
        code, response, _ = self.cli('--limit', '1', 'search', '--name', '__abs')
        self.assertEqual(code, 0)
        self.assertTrue(set(schema['$defs']['record']['required']) <= response['items'][0].keys())
        self.assertTrue(set(schema['$defs']['evidence']['required']) <= response['items'][0]['evidence'].keys())
