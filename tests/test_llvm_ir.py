import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import llvm_ir
from llvm_sources import Bitstream, bitcode_declarations, decode_iit, ELF
import query


class Bits:
    def __init__(self): self.bits=[]
    def put(self,n,width): self.bits.extend((n>>i)&1 for i in range(width))
    def vbr(self,n,width):
        while n >= 1<<(width-1):
            self.put((n&((1<<(width-1))-1))|(1<<(width-1)),width);n>>=width-1
        self.put(n,width)
    def align(self):
        while len(self.bits)%32:self.bits.append(0)
    def record(self,code,values):
        self.put(3,3);self.vbr(code,6);self.vbr(len(values),6)
        for v in values:self.vbr(v,6)
    def block(self,kind,child,width):
        self.put(1,width);self.vbr(kind,8);self.vbr(3,4);self.align()
        self.put(len(child.bits)//32,32);self.bits.extend(child.bits)
    def end(self):self.put(0,3);self.align()
    def bytes(self):return bytes(sum(self.bits[i+j]<<j for j in range(8)) for i in range(0,len(self.bits),8))


def fixture_bitcode():
    types=Bits();types.record(1,[4]);types.record(2,[]);types.record(7,[64]);types.record(25,[6]);types.record(21,[0,0,2,1]);types.end()
    module=Bits();module.record(1,[2]);module.block(17,types,3)
    name=b'llvm.hivm.TEST'
    module.record(8,[0,len(name),3,0,1,0,0,0]);module.end()
    strings=Bits();strings.put(2,3);strings.vbr(2,5)
    strings.put(1,1);strings.vbr(1,8);strings.put(0,1);strings.put(5,3)
    strings.put(4,3);strings.vbr(len(name),6);strings.align()
    for n in name:strings.put(n,8)
    strings.align();strings.end()
    top=Bits();top.block(8,module,2);top.block(23,strings,2)
    return b'BC\xc0\xde'+top.bytes()


class LLVMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=json.loads(llvm_ir.OUTPUT.read_text())
        cls.by_name={o['name']:o for o in cls.model['ops']}
        cls.forms={f['id']:f for f in cls.model['forms']}

    def test_container_declaration_not_call(self):
        m=bitcode_declarations(fixture_bitcode())
        f=m['functions'][0]
        self.assertEqual(f['name'],'llvm.hivm.TEST')
        self.assertEqual(f['signature'],'void (ptr addrspace(6), i64)')
        self.assertTrue(f['declaration'])
        self.assertEqual(m['body_analysis'],'not_scanned')
        with self.assertRaises(ValueError):Bitstream(b'bad').read()
        with self.assertRaises(ValueError):Bitstream(fixture_bitcode()[:-10]).read()
        with self.assertRaises(ValueError):ELF(b'bad')

    def test_registry_constraints_and_vendor_failure(self):
        self.assertEqual(decode_iit(0x50,b'')['signature'],'void (i64)')
        vector=decode_iit(0x80000000,bytes([47,6,27,6,2,0]))
        self.assertEqual(vector['return_type'],'<128 x half>')
        self.assertEqual(vector['parameters'],['ptr(as=6, element=i8)'])
        width=decode_iit(0x80000000,bytes([15,3,31,0,4,5,0]))
        self.assertEqual(width['parameters'],['same_vector_width(arg_info=0, element=i32)','i64'])
        unknown=decode_iit(0x80000000,bytes([99,0]))
        self.assertEqual(unknown['status'],'unparsed_vendor_encoding')
        self.assertNotIn('signature',unknown)

    def test_snapshot_and_bounded_identity(self):
        self.assertEqual(llvm_ir.validate_model(self.model),[])
        self.assertEqual(self.model['coverage']['identities']['registered'],12363)
        self.assertEqual(self.model['coverage']['failed_scans'],0)
        self.assertEqual(self.model['package']['unmatched_sources'],[])
        self.assertEqual(self.model['package']['verified_sources'],12)
        self.assertEqual(llvm_ir.identity('llvm.hivm.X'),llvm_ir.identity('llvm.hivm.X'))
        self.assertNotEqual(llvm_ir.identity('llvm.hivm.X'),llvm_ir.identity('llvm.hivm.X.i32'))

    def test_independent_signature_and_target_axes(self):
        barrier=self.by_name['llvm.hivm.BARRIER']
        self.assertEqual(barrier['identity_status'],'registered')
        self.assertEqual(barrier['target_status'],'c310_module_declaration')
        forms=[self.forms[f] for f in barrier['form_ids']]
        self.assertEqual({f['kind'] for f in forms},{'observed_signature','registry_constraints'})
        self.assertTrue(all(f['signature']=='void (i64)' for f in forms))
        unknown=next(o for o in self.model['ops'] if o['identity_status']=='registered' and o['target_status']=='unknown')
        self.assertTrue(unknown['form_ids'])
        self.assertEqual(set(unknown['verification'].values()),{'unverified'})

    def test_candidate_cannot_gain_signature(self):
        bad=copy.deepcopy(self.model)
        candidate=next(o for o in bad['ops'] if o['identity_status']=='candidate_only')
        candidate['form_ids']=[bad['forms'][0]['id']]
        self.assertIn('Candidate fabricated signature',llvm_ir.validate_model(bad))

    def test_web_packing_lossless(self):
        packed=llvm_ir.web_payload(self.model)
        for key in ('ops','forms'):
            t=packed[key]
            rows=[{k:v for k,v in zip(t['columns'],row) if v is not None} for row in t['rows']]
            if key=='ops':
                for row in rows:row['presence']={k:['not_scanned','scanned_absent','observed'][v] for k,v in zip(packed['presence_columns'],row['presence'])}
            self.assertEqual(rows,self.model[key])

    def test_queries_pagination_and_relations(self):
        def run(*args):return query.run(query.parser().parse_args(['--backend','llvm',*args]))
        a=run('--limit','2','search','--scope','all')
        b=run('--limit','2','--offset','2','search','--scope','all')
        self.assertEqual(a['next_offset'],2)
        self.assertFalse({i['id'] for i in a['items']}&{i['id'] for i in b['items']})
        op=self.by_name['llvm.hivm.BARRIER']
        self.assertTrue(run('forms',op['id'])['items'])
        self.assertTrue(all('source' in e for e in run('evidence',op['id'])['items']))
        self.assertTrue(any(e['kind']=='exact_llvm_symbol' for e in run('relations',op['id'])['items']))
        self.assertTrue(run('--limit','1','gaps','--gap','hivmc_a5_only_name')['items'])
        with self.assertRaises(ValueError):run('search','--chip','foo')
        self.assertIn('$defs',run('schema'))

    def test_unknown_types_and_names_remain_auditable(self):
        partial=[f for f in self.model['forms'] if f.get('signature_status')=='partial_vendor_types']
        self.assertEqual(len(partial),16)
        self.assertTrue(all('UNRESOLVED_TYPE_' in f['signature'] for f in partial))
        for f in partial:
            self.assertTrue(all(self.model['sources'][e['source_id']]['module']['unknown_types'] for e in f['evidence']))
        self.assertTrue(all(e['kind']!='exact_lowering' for e in self.model['relations'] if e['from'].startswith('ccec_op_')))

if __name__=='__main__':unittest.main()
