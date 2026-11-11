import importlib.util
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('catalog', ROOT / 'scripts/catalog.py')
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.errors, _, _ = catalog.extract_file(ROOT / 'tests/fixtures/interfaces.h', 'interfaces.h')

    def find(self, name):
        return next(r for r in self.records if r['name'] == name)

    def test_mismatched_toolkit_snapshot_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tools/bisheng_compiler/lib/clang/15.0.5/include').mkdir(parents=True)
            info = root / 'share/info/bisheng-compiler/version.info'
            info.parent.mkdir(parents=True)
            info.write_text('Version=9.3.0\ntimestamp=20261009_000000\n')
            with self.assertRaisesRegex(ValueError, 'metadata differs'):
                catalog.extract(root, root / 'catalog.json')

    def test_alias_namespace_and_variadic_signature(self):
        r = self.find('sample')
        self.assertEqual(r['namespace'], 'scalar')
        self.assertEqual(r['parameters'], ['...'])
        self.assertEqual(r['builtins'], ['__builtin_cce_sample'])

    def test_multiline_macro_variadics_and_token_paste(self):
        r = self.find('convert_f32')
        self.assertTrue(r['generated'])
        self.assertIn('__builtin_cce_convert_f32', r['builtins'])
        self.assertIn('sizeof(float) == 4', r['definition'])
        self.assertEqual(r['source']['line'], 13)
        self.assertEqual(r['source']['end_line'], 16)
        self.assertEqual(r['macro_sources'][0]['line'], 6)

    def test_all_conditional_branches_are_retained(self):
        self.assertIn('defined(ARCH_A)', self.find('convert_f32')['conditions'])
        branch = self.find('convert_i32')['conditions'][-1]
        self.assertIn('!((', branch)
        self.assertIn('ARCH_B', branch)
        self.assertIn('ARCH_A', self.find('barrier')['conditions'][-1])
        self.assertIn('ARCH_B', self.find('barrier')['conditions'][-1])

    def test_empty_macro_argument(self):
        self.assertEqual(self.find('copy')['parameters'], [])

    def test_forward_declaration_does_not_consume_following_type(self):
        self.assertEqual(self.find('Forward')['signature'], 'struct Forward')
        self.assertIn('int y', self.find('Pair')['signature'])

    def test_attribute_does_not_replace_typedef_name(self):
        self.assertEqual(self.find('vector_float')['kind'], 'type')
        self.assertEqual(self.find('Scalar')['kind'], 'type')

    def test_nested_template_closing_tokens(self):
        self.assertEqual(self.find('nested_template')['parameters'], ['T value'])

    def test_macro_interface_and_comment_filtering(self):
        self.assertEqual(self.find('set_flag')['kind'], 'interface_macro')
        self.assertEqual(catalog.pretty(catalog.tokens('"hello , world"')), '"hello , world"')
        self.assertFalse(any(r['name'] == 'fake' for r in self.records))
        self.assertTrue(any('Conditional macro' in e['reason'] for e in self.errors))
        self.assertFalse(any(r['name'] in ('from_target', 'from_other') for r in self.records))


if __name__ == '__main__':
    unittest.main()
