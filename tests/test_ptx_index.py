import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/zuomin/Projects/Compiler/work/experiments/ackb/ptx-index/source')
SPEC = importlib.util.spec_from_file_location('ptx_index', ROOT / 'scripts/ptx_index.py')
ptx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ptx)

FIXTURE = """
<html><head><title>PTX ISA 9.4 documentation</title></head><body>
<section id="instructions">
<h2><span class="section-number">9.7. </span><a class="reference internal" href="#">Instructions</a></h2>
<section id="sample-add">
<h3><span class="section-number">9.7.1.1. </span><a class="reference internal" href="#">Integer Arithmetic Instructions: <code class="docutils literal notranslate"><span class="pre">add</span></code></a></h3>
<p class="rubric">Syntax</p>
<pre class="literal-block">add.sat.s32 d, a, b;</pre>
<p class="rubric">Description</p>
<p>UNIQUEPROSE must stay outside the repository record.</p>
<p class="rubric">Target ISA Notes</p>
<p>Supported on all target architectures.</p>
<p>add.u16x2 requires sm_90 or higher.</p>
<p class="rubric">PTX ISA Notes</p>
<p>Introduced in PTX ISA version 1.0.</p>
<p>add.u16x2 introduced in PTX ISA version 8.0.</p>
</section>
<section id="sample-rounding">
<h3><span class="section-number">9.7.3.3. </span><a class="reference internal" href="#">Floating Point Instructions: <code>add</code></a></h3>
<p class="rubric">Syntax</p>
<pre>add.f32 d, a, b;</pre>
<p class="rubric">Target ISA Notes</p>
<p>Rounding modifiers have the following target requirements:</p>
<dl>
<dt>.rn, .rz</dt><dd>available for all targets</dd>
<dt>.rm, .rp</dt><dd>for add.f32, requires sm_20 or higher.</dd>
</dl>
<p>add.f32x2 requires sm_100 or higher.</p>
</section>
<section id="sample-topic">
<h3><span class="section-number">9.7.1. </span><a class="reference internal" href="#">Integer Arithmetic Instructions</a></h3>
<p>Group heading without an instruction syntax block.</p>
</section>
</section>
<section id="sample-pragma">
<h2><span class="section-number">11.2. </span><a class="reference internal" href="#">Pragma: <code>nounroll</code></a></h2>
<p class="rubric">Syntax</p>
<pre>.pragma "nounroll";</pre>
<p class="rubric">Target ISA Notes</p>
<p>Requires sm_20 or higher. Ignored for sm_1x targets.</p>
</section>
<section id="sample-directive-bare">
<h2><span class="section-number">11.9. </span><a class="reference internal" href="#">Directive: <code>.bare</code></a></h2>
<p class="rubric">Syntax</p>
<pre>.bare</pre>
</section>
<section id="thread-hierarchy">
<h2><span class="section-number">2.2. </span><a class="reference internal" href="#">Thread Hierarchy</a></h2>
</section>
<section id="register-state-space">
<h2><span class="section-number">5.1.1. </span><a class="reference internal" href="#">Register State Space</a></h2>
</section>
<section id="notices">
<h2><span class="section-number">14. </span><a class="reference internal" href="#">Notices</a></h2>
<p class="rubric">Syntax</p>
<pre>notice</pre>
</section>
</body></html>
"""


def support_for(lines):
    statements, unparsed, deferred = ptx.parse_target_blocks(lines)
    stored = [ptx.public_statement(item) for item in statements if item['relation'] != 'list_header']
    return ptx.support_from(stored, unparsed, deferred, True), stored, unparsed


def records_from(html):
    sections = ptx.parse_manual(html)
    by_id = {section['id']: section for section in sections}
    found = {}
    for section in sections:
        ancestors = ptx.ancestor_ids(section, by_id)
        kind = ptx.classify(section, ancestors)
        found[section['id']] = (kind, section)
    return found


class ParserTests(unittest.TestCase):
    def test_target_statements_keep_sm_89_distinct_from_later_and_suffixed_targets(self):
        self.assertEqual(support_for(['Supported on all target architectures.'])[0], 'documented_supported')
        self.assertEqual(support_for(['Requires sm_80 or higher.'])[0], 'documented_supported')
        self.assertEqual(support_for(['Requires sm_90 or higher.'])[0], 'documented_not_supported')
        self.assertEqual(support_for(['Requires sm_90a.'])[0], 'documented_not_supported')
        self.assertEqual(
            support_for(['Requires sm_100f or higher in the same family.'])[0],
            'documented_not_supported',
        )
        mixed, stored, unparsed = support_for([
            'Supported on all target architectures.',
            'add.u16x2 requires sm_90 or higher.',
        ])
        self.assertEqual(mixed, 'partial')
        self.assertEqual(unparsed, [])
        self.assertIn('sm_90', [item['sm'] for item in stored])

    def test_same_subject_exclusion_overrides_an_older_minimum(self):
        status, stored, _ = support_for([
            'shfl requires sm_30 or higher.',
            'shfl is not supported on sm_70 or higher starting PTX ISA version 6.4.',
        ])
        self.assertEqual(status, 'documented_not_supported')
        self.assertEqual(
            [item['relation'] for item in stored],
            ['minimum_sm', 'excluded_minimum'],
        )

    def test_legacy_sm_1x_sentence_does_not_deny_sm_89(self):
        status, stored, unparsed = support_for(['Requires sm_20 or higher. Ignored for sm_1x targets.'])
        self.assertEqual(status, 'documented_supported')
        self.assertEqual(unparsed, [])
        self.assertEqual(stored[0]['sm'], 'sm_20')
        self.assertEqual(stored[1]['relation'], 'legacy_target_limit')

    def test_missing_underscore_and_family_list_are_structured(self):
        status, stored, _ = support_for(['cvt with .e4m3x2/.e5m2x2 requires sm89 or higher.'])
        self.assertEqual(status, 'documented_supported')
        self.assertEqual(stored[0]['sm'], 'sm_89')
        listed, items, unparsed = support_for([
            'Qualifier .kind::i8 is supported on following architectures:',
            'sm_90a',
            'sm_100a',
        ])
        self.assertEqual(listed, 'documented_not_supported')
        self.assertEqual(unparsed, [])
        self.assertEqual([item['sm'] for item in items], ['sm_90a', 'sm_100a'])
        self.assertTrue(all(item['subject'] for item in items))

    def test_unparsed_text_and_cross_reference_do_not_become_support(self):
        status, _, unparsed = support_for(['This qualifier depends on the phase of the moon.'])
        self.assertEqual(status, 'unknown')
        self.assertEqual(set(unparsed[0]), {'sha256', 'chars'})
        self.assertNotIn('moon', json.dumps(unparsed))
        deferred, _, _ = support_for([
            'Supported on all target architectures.',
            'For Target ISA details on matrix shape, check Target ISA Note.',
        ])
        self.assertEqual(deferred, 'partial')

    def test_ptx_version_facts_are_structured_and_narrative_sentences_are_not_copied(self):
        statements, unparsed = ptx.parse_ptx_blocks([
            'Introduced in PTX ISA version 8.6. (Renamed to sm_110)',
            'Deprecated in PTX ISA version 6.0 in favor of shfl.sync.',
            'Not supported in PTX ISA version 6.4 for .target sm_70 or higher.',
            'Modifier .aligned is required from PTX ISA version 6.3 onwards, and considered implicit in PTX ISA versions less than 6.3.',
            'Kernel function addresses should only be used in the context of CUDA Dynamic Parallelism system calls.',
        ])
        self.assertEqual(statements[0]['kind'], 'introduced')
        self.assertEqual(statements[0]['renamed_to'], 'sm_110')
        self.assertEqual(statements[1]['kind'], 'deprecated')
        self.assertIn('shfl.sync', statements[1]['subject'])
        denied = next(item for item in statements if item['kind'] == 'not_supported_on_target')
        self.assertEqual(denied['sm'], 'sm_70')
        self.assertEqual(denied['version'], '6.4')
        self.assertTrue(any(item['kind'] == 'required_since' and item['version'] == '6.3' for item in statements))
        self.assertEqual(len(unparsed), 1)
        self.assertNotIn('Dynamic Parallelism', json.dumps(unparsed))

    def test_fixture_html_classifies_sections_and_omits_description_prose(self):
        found = records_from(FIXTURE)
        self.assertEqual(found['sample-add'][0], 'instruction')
        self.assertEqual(found['sample-topic'][0], 'instruction_topic')
        self.assertEqual(found['sample-pragma'][0], 'directive')
        self.assertEqual(found['sample-directive-bare'][0], 'directive')
        self.assertEqual(found['thread-hierarchy'][0], 'execution_model')
        self.assertEqual(found['register-state-space'][0], 'state_space')
        self.assertEqual(found['notices'][0], 'notice')

        add = ptx.note_record(found['sample-add'][1], True)
        blob = json.dumps(add)
        self.assertNotIn('UNIQUEPROSE', blob)
        self.assertEqual(add['sm_89']['support'], 'partial')
        self.assertEqual(add['syntax']['line_count'], 1)
        self.assertEqual(len(add['description']['sha256']), 64)
        self.assertEqual(add['compile_verification'], 'unverified')
        self.assertEqual(add['experiments'], [])
        self.assertEqual(add['ptx_isa']['statements'][0]['version'], '1.0')
        self.assertEqual(ptx.entry_id('sample-add', '9.7.1.1.'), add['entry_id'])
        self.assertTrue(add['entry_id'].startswith('ptx_'))

        rounding = ptx.note_record(found['sample-rounding'][1], True)
        self.assertEqual(rounding['sm_89']['support'], 'partial')
        self.assertEqual(rounding['target_isa']['unparsed'], [])

        pragma = ptx.note_record(found['sample-pragma'][1], True)
        self.assertEqual(pragma['sm_89']['support'], 'documented_supported')
        bare = ptx.note_record(found['sample-directive-bare'][1], True)
        self.assertEqual(bare['sm_89']['support'], 'unknown')
        self.assertEqual(bare['target_isa']['unparsed'][0].keys(), {'sha256', 'chars'})


class IndexIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ptx.load_tree(ROOT / 'data/ptx')

    def test_committed_index_matches_its_own_scan(self):
        self.assertEqual(ptx.validate_tree(self.tree), [])
        scan = self.tree['scan']
        self.assertEqual(scan['html_sections'], 743)
        self.assertEqual(scan['instructions'], 221)
        self.assertEqual(scan['execution_sections'], 77)
        self.assertEqual(sum(scan['kinds'].values()), 743)
        self.assertEqual(scan['unparsed_target_blocks'], 0)
        self.assertEqual(scan['unparsed_ptx_isa_sentences'], 2)
        self.assertEqual(scan['instruction_sm_89_support']['unknown'], 0)
        self.assertGreater(scan['instruction_sm_89_support']['documented_not_supported'], 0)
        self.assertGreater(scan['instruction_sm_89_support']['partial'], 0)
        self.assertFalse(scan['text_stored'])

    def test_manual_oracles_do_not_treat_the_whole_isa_as_sm_89(self):
        instructions = {item['anchor']: item for item in self.tree['instructions']}
        expected = {
            'integer-arithmetic-instructions-add': 'partial',
            'floating-point-instructions-add': 'partial',
            'parallel-synchronization-and-communication-instructions-bar-warp-sync': 'documented_supported',
            'parallel-synchronization-and-communication-instructions-barrier-cluster': 'documented_not_supported',
            'parallel-synchronization-and-communication-instructions-membar': 'partial',
            'data-movement-and-conversion-instructions-shfl': 'documented_not_supported',
            'data-movement-and-conversion-instructions-cvt': 'partial',
            'warp-level-matrix-instructions-mma': 'partial',
            'asynchronous-warpgroup-level-matrix-instructions-wgmma-mma': 'documented_not_supported',
            'tcgen05-mma-instructions-mma': 'documented_not_supported',
        }
        for anchor, status in expected.items():
            record = instructions[anchor]
            self.assertEqual(record['sm_89']['support'], status, anchor)
            self.assertEqual(record['experiments'], [])
            self.assertEqual(record['compile_verification'], 'unverified')
            self.assertEqual(record['runtime_verification'], 'unverified')
        mma = instructions['warp-level-matrix-instructions-mma']['target_isa']['statements']
        e4 = [item for item in mma if item.get('sm') == 'sm_89']
        self.assertTrue(e4 and all(item['applies'] == 'yes' for item in e4))
        f64_wide = [
            item for item in mma
            if item.get('sm') == 'sm_90' and item.get('subject') and 'm16n8k16' in item['subject']
        ]
        self.assertTrue(f64_wide and all(item['applies'] == 'no' for item in f64_wide))
        for record in self.tree['instructions'] + self.tree['directives'] + self.tree['special_registers']:
            for value in json.dumps(record).split('"'):
                self.assertLessEqual(len(value), 240)

    def test_source_pin_separates_isa_9_4_from_sm_89_and_the_laptop_sku(self):
        source = self.tree['source']
        self.assertEqual(source['isa']['version'], '9.4')
        self.assertEqual(source['isa']['cuda_archive'], '13.4.3')
        self.assertNotEqual(source['isa']['version'], source['query_target']['ptx_target'])
        self.assertEqual(source['query_target']['ptx_target'], 'sm_89')
        self.assertFalse(source['query_target']['sku_evidence']['cuda_gpu_table']['row']['names_rtx_4080_laptop'])
        self.assertTrue(source['query_target']['sku_evidence']['cuda_gpu_table']['row']['names_geforce_rtx_4080'])
        history = source['release_history']
        self.assertEqual(history['sm_89_introduced']['ptx_isa'], '7.8')
        self.assertIn('sm_89', history['sm_89_introduced']['targets'])
        self.assertIn('sm_89', history['isa_9_4']['targets'])
        self.assertEqual(source['isa']['html']['sha256'], ptx.PINNED['html']['sha256'])
        self.assertEqual(source['isa']['pdf']['sha256'], ptx.PINNED['pdf']['sha256'])
        self.assertEqual(source['query_target']['experiments'], [])

    def test_depth_notes_cite_real_sections_and_do_not_claim_experiments(self):
        catalog = {item['anchor']: item['section_number'].rstrip('.') for item in self.tree['sections']}
        self.assertEqual(
            [note['id'] for note in self.tree['notes']],
            [
                'note_execution_hierarchy',
                'note_state_spaces',
                'note_synchronization',
                'note_selected_instruction_constraints',
            ],
        )
        for note in self.tree['notes']:
            self.assertEqual(note['language'], 'zh')
            self.assertEqual(note['depth'], 'selected')
            self.assertEqual(note['experiments'], [])
            self.assertTrue(note['unknowns'])
            self.assertLessEqual(len(note['body']), 1200)
            for citation in note['citations']:
                self.assertEqual(catalog[citation['anchor']], citation['section'])

    def test_reextract_matches_the_committed_index_when_the_pin_is_present(self):
        html = SOURCE / ptx.PINNED['html']['name']
        if not html.is_file():
            self.skipTest('pinned PTX HTML is not on this machine')
        with TemporaryDirectory() as directory:
            output = Path(directory)
            ptx.extract(
                html,
                SOURCE / ptx.PINNED['pdf']['name'],
                SOURCE / ptx.PINNED['gpus']['name'],
                SOURCE / ptx.PINNED['ada']['name'],
                SOURCE / ptx.PINNED['platform']['name'],
                output,
            )
            for name in ('source', 'scan', 'sections', 'instructions', 'execution', 'directives', 'special_registers', 'notes'):
                committed = (ROOT / 'data/ptx' / f'{name}.json').read_bytes()
                fresh = (output / f'{name}.json').read_bytes()
                self.assertEqual(hashlib.sha256(committed).hexdigest(), hashlib.sha256(fresh).hexdigest(), name)


if __name__ == '__main__':
    unittest.main()
