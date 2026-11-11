import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compatibility import evaluate, analyze


class CompatibilityTests(unittest.TestCase):
    def test_unknown_is_not_undefined(self):
        self.assertIsNone(evaluate('!defined(OTHER)', {}))
        self.assertIsNone(evaluate('__NPU_ARCH__ == 3510', {'__CCE_AICORE__': 310}))

    def test_boolean_short_circuit_and_negation(self):
        macros = {'__CCE_AICORE__': 220}
        self.assertEqual(evaluate('__CCE_AICORE__ == 220 || OTHER', macros), True)
        self.assertEqual(evaluate('__CCE_AICORE__ >= 300 && OTHER', macros), False)
        self.assertEqual(evaluate('!(__CCE_AICORE__ != 220)', macros), True)
        self.assertIsNone(evaluate('__CCE_AICORE__ == 220 && OTHER', macros))

    def test_defined_spacing_and_unsupported(self):
        self.assertEqual(evaluate('defined __DAV_C220__', {'__DAV_C220__': 1}), True)
        self.assertIsNone(evaluate('function(220)', {}))
        self.assertIsNone(evaluate('X ? 1 : 0', {}))

    def test_per_overload_and_conditional_deprecation(self):
        records = []
        for index, (condition, signature) in enumerate([
            ('__CCE_AICORE__ == 220', 'void op(int)'),
            ('__CCE_AICORE__ == 310', 'DEPRECATED_AFTER_V210 void op(float)'),
            ('OTHER', 'NOT_DEPRECATED void op(double)')]):
            records.append({'name': 'op', 'kind': 'interface', 'conditions': [condition], 'signature': signature,
                            'source': {'file': 'test.h', 'line': 40 + index}})
        data = analyze({'records': records, 'version': 'test'})
        self.assertEqual(records[0]['compatibility']['profiles']['__CCE_AICORE__=220'], 'matches')
        self.assertEqual(records[1]['compatibility']['profiles']['__CCE_AICORE__=220'], 'excluded')
        self.assertEqual(records[2]['compatibility']['profiles']['__CCE_AICORE__=220'], 'unknown')
        self.assertEqual(records[1]['deprecation']['status'], 'conditional')
        self.assertEqual(records[2]['deprecation']['status'], 'unmarked')
        self.assertEqual(data['compatibility']['versions'], ['test'])

class VersionComparisonTests(unittest.TestCase):
    def test_overload_condition_changes_are_not_name_removal(self):
        from compare import compare
        def dataset(version, condition):
            return {'version': version, 'records': [{'name': 'op', 'kind': 'interface', 'signature': 'void op(int)',
                    'conditions': [condition], 'source': {'file': 'a.h', 'line': 40}}]}
        result = compare(dataset('old', '__CCE_AICORE__ == 220'), dataset('new', '__CCE_AICORE__ == 310'))
        self.assertEqual(result['added'], [])
        self.assertEqual(result['removed'], [])
        self.assertEqual(len(result['changed']), 1)

class TargetMetadataTests(unittest.TestCase):
    def test_targets_preserve_source_and_do_not_guess_missing_arch(self):
        from tempfile import TemporaryDirectory
        from targets import extract
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'x86_64-linux/data/platform_config'
            config.mkdir(parents=True)
            entry = config / 'chip.ini'
            entry.write_text('[version]\nSoC_version=Example\nNpuArch=2201\nCCEC_CUBE_version=dav-c220-cube\n')
            result = extract(root)
            self.assertEqual(result[0]['npu_arch'], 2201)
            self.assertEqual(result[0]['cores']['ccec_cube_version'], 'dav-c220-cube')
            self.assertFalse(result[0]['source']['package_verified'])
            self.assertEqual(len(result[0]['source']['sha256']), 64)
            entry.write_text('[version]\nSoC_version=Example\n')
            with self.assertRaisesRegex(ValueError, 'NpuArch'):
                extract(root)
