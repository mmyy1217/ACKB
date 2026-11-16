"""Integration checks for backend isolation, evidence and bounded traversal."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from query import parser, run


def query(*argv):
    return run(parser().parse_args(argv))


class KnowledgeTests(unittest.TestCase):
    def test_ptx_coverage_and_pagination(self):
        result = query('--backend', 'ptx', '--limit', '2', 'search')
        self.assertEqual(result['total'], 221)
        self.assertEqual(result['next_offset'], 2)
        self.assertEqual(query('--backend', 'ptx', 'search', '--kind', 'all')['total'], 743)
        self.assertEqual(query('--backend', 'ptx', 'targets', '--name', 'nonexistent')['total'], 0)

    def test_ptx_constraints_and_evidence(self):
        result = query('--backend', 'ptx', 'search', '--name', 'mma')['items'][0]
        self.assertEqual(result['target_assessment']['support'], 'partial')
        record = query('--backend', 'ptx', 'get', result['entry_id'])['items'][0]
        self.assertTrue(record['target_isa']['statements'])
        self.assertEqual(len(record['evidence'][0]['source_sha256']), 64)
        self.assertIn('#', record['evidence'][0]['url'])
        self.assertEqual(record['experiments'], [])
        with self.assertRaises(ValueError):
            query('--backend', 'ptx', 'builtins')
        with self.assertRaises(ValueError):
            query('--backend', 'ptx', 'get', result['entry_id'], '--support', 'partial')

    def test_notes_cite_sections(self):
        notes = query('--backend', 'ptx', 'topics')
        self.assertEqual(notes['total'], 15)
        links = query('--backend', 'ptx', 'relations', notes['items'][0]['id'])
        self.assertTrue(links['items'])
        self.assertTrue(all(x['relation'] == 'cites_section' for x in links['items']))

    def test_ccec_knowledge_and_legacy(self):
        with self.assertRaises(ValueError):
            query('get', 'ccec_topic_compute', '--chip', 'Ascend950PR_9579')
        self.assertEqual(query('topics')['total'], 8)
        self.assertEqual(query('builtins')['total'], 2222)
        record = query('get', 'ccec_topic_compute')['items'][0]
        self.assertTrue(record['evidence_truncated'])
        evidence = query('--offset', '3', '--limit', '2', 'evidence', record['id'])
        self.assertEqual(len(evidence['items']), 2)
        self.assertEqual(evidence['offset'], 3)
        self.assertEqual(query('search', '--name', 'copy_gm_to_cbuf')['schema_version'], 'cce-ops.query.v1')

    def test_schema_and_unknown(self):
        self.assertEqual(query('--backend', 'ptx', 'schema')['properties']['schema_version']['const'], 'ackb.knowledge-query.v1')
        with self.assertRaises(ValueError):
            query('--backend', 'ptx', 'get', 'missing')


if __name__ == '__main__':
    unittest.main()
