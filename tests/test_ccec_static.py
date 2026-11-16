"""Architecture selector proofs stay separate from lexical references and support claims."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccec_support import Support
from ccec_static import OUTPUT, architecture_routes, StaticAnalysis, validate, conditions_result


class RouteTests(unittest.TestCase):
    def test_explicit_selector_propagates_and_rejects_other_arch(self):
        files = {f: {'guards': []} for f in ['base.h', 'a.h', 'b.h', 'conditional.h', 'other.h']}
        edges = [
            {'file': 'base.h', 'resolved_relative_path': 'a.h', 'conditions': ['__NPU_ARCH__ == 3510']},
            {'file': 'a.h', 'resolved_relative_path': 'b.h', 'conditions': []},
            {'file': 'b.h', 'resolved_relative_path': 'a.h', 'conditions': []},
            {'file': 'a.h', 'resolved_relative_path': 'conditional.h', 'conditions': ['defined(FLAG)']},
            {'file': 'base.h', 'resolved_relative_path': 'other.h', 'conditions': ['__NPU_ARCH__ == 2201']}]
        data = {'files': files, 'includes': edges}
        routes = architecture_routes(data, 3510)
        self.assertTrue(routes['a.h']['state'])
        self.assertEqual(routes['b.h']['edges'], [0, 1])
        self.assertIsNone(routes['conditional.h']['state'])
        self.assertNotIn('other.h', routes)
        self.assertNotIn('a.h', architecture_routes(data, 2201))

    def test_unknown_is_not_absent_and_no_directory_inference(self):
        self.assertIsNone(conditions_result(['!defined(__DAV_L311__)'], 3510))
        data = {'files': {'dav_3510/a.h': {'guards': []}}, 'includes': []}
        self.assertEqual(architecture_routes(data, 3510), {})

    def test_header_guard_removal_does_not_remove_feature_flags(self):
        files = {'a.h': {'guards': [{'macro': 'A_H', 'condition': '!defined(A_H)'},
                                   {'macro': 'FEATURE', 'condition': '!defined(FEATURE)'}]},
                 'b.h': {'guards': []}}
        edge = {'file': 'a.h', 'resolved_relative_path': 'b.h', 'conditions': ['!defined(A_H)', '__NPU_ARCH__ == 3510']}
        self.assertTrue(architecture_routes({'files': files, 'includes': [edge]}, 3510)['b.h']['state'])
        edge['conditions'].append('!defined(FEATURE)')
        self.assertEqual(architecture_routes({'files': files, 'includes': [edge]}, 3510), {})


class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = Support()
        cls.data = json.loads(OUTPUT.read_text())

    def test_every_record_and_architecture_has_an_explicit_outcome(self):
        self.assertEqual(validate(self.data, self.support), [])
        self.assertEqual(self.data['coverage'], {'records': 5714, 'architectures': 14, 'chips': 74, 'assessments': 79996})
        self.assertEqual(sum(self.data['counts']['3510'].values()), 5714)

    def test_real_cube_reference_has_selector_chain(self):
        analysis = StaticAnalysis(self.support)
        record = self.support.db.by_id['960c673e040dc702bc0a']
        result = analysis.assess(record, 3510)
        self.assertEqual(result['state'], 'architecture_reference')
        self.assertIn('ASCEND_IS_AIC', result['core_guards'])
        trace = analysis.trace(result, 3510)
        self.assertTrue(trace[0]['architecture_selector_path'])
        self.assertTrue(any('3510' in ' '.join(e['conditions']) for e in trace[0]['architecture_selector_path']))

    def test_conflicts_and_absent_macro_definitions_stay_visible(self):
        self.assertGreater(self.data['counts']['3510']['source_conflict'], 0)
        audit = self.data['macro_audit']['3510']['__CCE_AICORE__']
        self.assertEqual(audit['finding'], 'no_definition_in_scanned_headers')
        self.assertNotIn('not', self.data['macro_audit']['3510'])
        damaged = copy.deepcopy(self.data)
        damaged['architectures'].pop('3510')
        self.assertIn('Incomplete architecture coverage', validate(damaged, self.support))
