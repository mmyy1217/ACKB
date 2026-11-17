import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from llvm_calls import direct_calls
from llvm_a5 import classify
import llvm_ir
import query
from tests.test_llvm_ir import Bits


def fixture(instructions):
    types=Bits();types.record(1,[4]);types.record(2,[]);types.record(7,[32]);types.record(21,[0,0]);types.record(21,[0,1]);types.end()
    names=[b'llvm.hivm.VOID',b'llvm.hivm.RESULT',b'caller'];strings_data=b''.join(names)
    module=Bits();module.record(1,[2]);module.block(17,types,3)
    start=0
    for name,tid,decl in zip(names,[2,3,2],[1,1,0]):
        module.record(8,[start,len(name),tid,0,decl,0,0,0]);start+=len(name)
    body=Bits();body.record(1,[1])
    for code,values in instructions:body.record(code,values)
    body.record(10,[]);body.end();module.block(12,body,3);module.end()
    strings=Bits();strings.put(2,3);strings.vbr(2,5);strings.put(1,1);strings.vbr(1,8);strings.put(0,1);strings.put(5,3)
    strings.put(4,3);strings.vbr(len(strings_data),6);strings.align()
    for n in strings_data:strings.put(n,8)
    strings.align();strings.end();top=Bits();top.block(8,module,2);top.block(23,strings,2)
    return b'BC\xc0\xde'+top.bytes()


class A5Tests(unittest.TestCase):
    def test_relative_ids_void_and_value_return(self):
        m=direct_calls(fixture([(34,[0,32768,2,3]),(34,[0,32768,3,2]),(34,[0,32768,2,4])]))
        self.assertEqual([c['callee'] for c in m['calls']],['llvm.hivm.VOID','llvm.hivm.RESULT','llvm.hivm.VOID'])
        self.assertTrue(all(c['caller']=='caller' for c in m['calls']))
        self.assertEqual(m['issues'],[])

    def test_declared_but_not_called(self):
        self.assertEqual(direct_calls(fixture([]))['calls'],[])

    def test_unknown_record_discards_body(self):
        m=direct_calls(fixture([(34,[0,32768,2,3]),(63,[])]))
        self.assertEqual(m['calls'],[]);self.assertIn('Unsupported',m['issues'][0]['reason'])

    def test_wrong_type_does_not_create_evidence(self):
        m=direct_calls(fixture([(34,[0,32768,3,3])]))
        self.assertEqual(m['calls'],[]);self.assertIn('mismatch',m['issues'][0]['reason'])

    def test_external_and_name_hints_never_gain_package_status(self):
        base={'domain':'target_intrinsic','identity_status':'lowering_reference','presence':{'dialect':'observed'},'evidence':[]}
        self.assertEqual(classify(base,[])['status'],'external_only')
        base['presence']['hivmc_a5']='observed';self.assertEqual(classify(base,[])['status'],'a5_name_only')
        self.assertFalse(classify(base,[])['package_evidence'])
        self.assertEqual(classify(base,[])['support'],'not_established')

    def test_snapshot_call_form_and_target_integrity(self):
        m=json.loads(llvm_ir.OUTPUT.read_text());self.assertEqual(llvm_ir.validate_model(m),[])
        self.assertTrue(m['a5_call_table']['rows']);self.assertEqual(m['target_mapping']['npu_arch'],3510)
        selected=[o for o in m['ops'] if llvm_ir.default_visible(o)]
        self.assertTrue(all(o['static_target']['status'] in ('c310_direct_call','c310_declaration') for o in selected))
        bad=copy.deepcopy(m);bad['ops'][0]['static_target']['support']='supported'
        self.assertIn('A5 classification mismatch',llvm_ir.validate_model(bad))

    def test_unresolved_is_paged_and_source_backed(self):
        result=query.run(query.parser().parse_args(['--backend','llvm','--limit','2','unresolved']))
        self.assertEqual(len(result['items']),2)
        self.assertEqual(result['next_offset'],2)
        self.assertTrue(all(i['source']['sha256'] and i['bit_offset'] and i['caller'] for i in result['items']))


if __name__=='__main__':unittest.main()
