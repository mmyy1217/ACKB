import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ptx_forms import expand
from nvvm_index import Reader,validate,OUTPUT
import json
class Sources(unittest.TestCase):
    def test_ptx_wide_restriction(self):
        names=expand('mul.mode.type d,a,b;\n.mode = { .lo, .wide };\n.type = { .u32, .u64 };')
        self.assertIn('mul.wide.u32',names);self.assertNotIn('mul.wide.u64',names)
    def test_optional_modifiers(self):
        names=expand('add{.rnd}{.ftz}{.sat}.f32 d,a,b;\n.rnd = { .rn, .rz };')
        self.assertIn('add.rn.ftz.sat.f32',names)
    def test_nvvm(self):
        d=json.loads(OUTPUT.read_text());validate(d)
        self.assertTrue(any(r['name']=='llvm.nvvm.barrier0' for r in d['records']))
    def test_no_nvvm_fabricated_signatures(self):
        d=json.loads(OUTPUT.read_text())
        for r in d['records']:
            for signature in r['signatures']:self.assertIn(r['name'],signature)
