#!/usr/bin/env python3
"""Extract versioned LLVM target metadata without executing the compiler."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

from catalog import ROOT, VERSION, file_digest, family_for
from llvm_sources import ELF, bitcode_declarations, decode_iit

OUTPUT = ROOT / 'data/llvm' / VERSION / 'index.json'
PROTOCOL = 'ackb.llvm.query.v1'
TOOLS = {'hivmc_a5':'tools/bishengir/bin/hivmc-a5',
         'ccec':'tools/bisheng_compiler/bin/ccec',
         'llc':'tools/bisheng_compiler/lib/libbisheng-llc.so'}
LIMITATIONS = [
    '注册表是本版本编译器的跨架构注册范围，不是 950 支持清单，也不是硬件 ISA 全集。',
    '950 包内证据来自 c310 模块；A5 相关线索还包括 hivmc-a5 中的名称。模块核归属不等于对其他核的排除结论。',
    'IIT 为按上游 LLVM 15 格式解释的类型约束，保留原编码；未知厂商编码不补造签名。',
    'c310 函数体只追踪已解析的直接调用；间接调用与未知编码单列。模块调用不证明入口可达、目标编译通过或运行验证。',
    'CCEDialect 是独立外部工程；名称候选关联不等于编译器 lowering 证明。',
    'gaps 表示索引缺口，不能据此声称发现未公开硬件能力。',
]
DOMAIN_LABELS = {'target_intrinsic':'目标 Intrinsic','standard_intrinsic':'标准 LLVM Intrinsic','ordinary_ir':'普通 LLVM IR'}
PATTERN = re.compile(rb'(?<![A-Za-z0-9_.])llvm\.(?:hivm|cce)\.[A-Za-z0-9_.]+')


def identity(name, domain='target_intrinsic'):
    return 'llvm_ir_' + hashlib.sha256((domain+'\0'+name).encode()).hexdigest()[:20]


def family(name):
    n = name.lower().replace('.', '_')
    if any(x in n for x in ('mov_', 'dma', 'copy_')): return '搬运 / DMA'
    if any(x in n for x in ('mad', 'mma')): return '矩阵 / Cube'
    if any(x in n for x in ('vld', 'vst', 'load', 'store', 'gather', 'scatter', 'dcci')): return '访存 / 布局'
    if any(x in n for x in ('barrier', 'fence', 'flag', 'wait', 'sync')): return '同步 / 流水'
    return family_for(n)


def extract(toolkit, output=OUTPUT):
    previous = json.loads(output.read_text()) if output.exists() else {}
    sources, ops, forms, edges, scans = {}, {}, {}, [], []
    def source(key, path):
        p = toolkit/path
        sources[key] = {'id':key, 'origin':'cann', 'path':path, 'sha256':file_digest(p), 'bytes':p.stat().st_size,
                        'package_status':'not_verified'}
        return p
    def get(name, domain=None):
        domain = domain or ('target_intrinsic' if name.startswith(('llvm.hivm.','llvm.cce.')) else 'standard_intrinsic')
        oid = identity(name, domain)
        if oid not in ops:
            ops[oid] = {'id':oid, 'name':name, 'domain':domain, 'family':family(name), 'identity_status':'candidate_only',
                        'target_status':'unknown', 'presence':{}, 'evidence':[], 'form_ids':[], 'a5_source_lead':False,
                        'verification':{'compile':'unverified','runtime':'unverified','performance':'unverified'}}
        return ops[oid]
    def form(op, kind, payload, sid, location):
        key = hashlib.sha256(json.dumps([op['id'],kind,payload],sort_keys=True).encode()).hexdigest()[:20]
        fid = 'llvm_form_'+key
        if fid not in forms:
            forms[fid] = {'id':fid,'op_id':op['id'],'kind':kind,**payload,'evidence':[]}
            op['form_ids'].append(fid)
        forms[fid]['evidence'].append({'source_id':sid,**location})
    for sid, path in TOOLS.items():
        p = source(sid,path)
        raw = p.read_bytes()
        names = {}
        for match in PATTERN.finditer(raw):
            name = match[0].decode()
            names.setdefault(name,match.start())
        for name, offset in names.items():
            op = get(name)
            op['presence'][sid] = 'observed'
            op['evidence'].append({'kind':'binary_string','source_id':sid,'byte_offset':offset})
            if sid == 'hivmc_a5': op['a5_source_lead'] = True
        scans.append({'source_id':sid,'method':'bounded_name_regex','names':len(names),'status':'complete'})
        if sid == 'llc':
            registry, long_table, long_offset = ELF(raw).registry()
            selected = [r for r in registry if r['name'].startswith(('llvm.hivm.','llvm.cce.'))]
            scans.append({'source_id':sid,'method':'elf_intrinsic_registry','all_target_registry_slots':len(registry),
                          'hivm_cce_registered':len(selected),'status':'complete'})
            for r in selected:
                op = get(r['name'])
                op['identity_status'] = 'registered'
                op['registry'] = r
                op['evidence'].append({'kind':'registry','source_id':sid,'byte_offset':r['name_offset'],
                                       'registry_id':r['registry_id'],'type_offset':r['type_offset']})
                decoded = decode_iit(r['type_word'],long_table)
                form(op,'registry_constraints',{**decoded,'overloaded':r['overloaded']},sid,
                     {'byte_offset':r['type_offset'],'long_table_offset':long_offset,
                      'encoding_word':r['type_word']})
    bitcodes = sorted((toolkit/'tools/bishengir/lib').glob('*.c310.*.bc')) + [toolkit/'tools/bisheng_compiler/lib/malloc.bc']
    for p in bitcodes:
        sid = 'bc_'+p.name.replace('.','_')
        source(sid,p.relative_to(toolkit).as_posix())
        try:
            module = bitcode_declarations(p.read_bytes())
        except (ValueError,IndexError,StopIteration,UnicodeError) as error:
            scans.append({'source_id':sid,'method':'bitcode_declarations','status':'failed','error':str(error)})
            continue
        sources[sid]['module'] = {k:v for k,v in module.items() if k!='functions'}
        scans.append({'source_id':sid,'method':'bitcode_declarations','status':'complete','llvm_declarations':len(module['functions'])})
        for fn in module['functions']:
            op = get(fn['name'])
            if op['identity_status'] == 'candidate_only': op['identity_status'] = 'declaration_observed'
            op['presence'][sid] = 'observed'
            op['a5_source_lead'] |= '.c310.' in p.name
            if '.c310.' in p.name: op['target_status'] = 'c310_module_declaration'
            op['evidence'].append({'kind':'bitcode_declaration','source_id':sid,'bit_offset':fn['bit_offset'],'declaration':fn['declaration']})
            form(op,'observed_signature',{k:fn[k] for k in ('return_type','parameters','vararg','signature','signature_status')},sid,
                 {'bit_offset':fn['bit_offset'],'type_id':fn['type_id']})
    # Registered overloaded base names are kept separate from concrete observed symbols.
    bases = sorted((o for o in ops.values() if o.get('registry',{}).get('overloaded')),key=lambda o:-len(o['name']))
    for op in list(ops.values()):
        if op['identity_status']=='registered': continue
        for base in bases:
            if op['name'].startswith(base['name']+'.'):
                edges.append({'from':op['id'],'to':base['id'],'kind':'overload_name_candidate'})
                break
    # Absence means only that this exact spelling was absent from that completed scan.
    for op in ops.values():
        for sid in [*TOOLS,*[x['source_id'] for x in scans if x['method']=='bitcode_declarations' and x['status']=='complete']]:
            op['presence'].setdefault(sid,'scanned_absent' if op['domain']=='target_intrinsic' or sid.startswith('bc_') else 'not_scanned')
    edges = list({json.dumps(e,sort_keys=True):e for e in edges}.values())
    model = {'schema_version':'ackb.llvm.index.v1','version':VERSION,'target':'Ascend950PR_9579',
             'generator_sha256':generator_digest(),
             'sources':sources,'ops':sorted(ops.values(),key=lambda o:o['name']),
             'forms':sorted(forms.values(),key=lambda f:f['id']),'relations':sorted(edges,key=lambda e:(e['from'],e['to'],e['kind'])),
             'scans':scans,'limitations':LIMITATIONS,
             'format_reference':{'url':'https://github.com/llvm/llvm-project/blob/llvmorg-15.0.5/llvm/lib/IR/Function.cpp','scope':'IIT interpretation, not vendor support authority'}}
    from llvm_a5 import enrich
    enrich(model, toolkit)
    model['coverage']=coverage(model)
    # Reuse original-package comparisons only for identical versioned bytes.
    if previous.get('version') == VERSION and previous.get('package'):
        for sid,s in sources.items():
            old = previous.get('sources',{}).get(sid,{})
            if s['sha256']==old.get('sha256') and s['path']==old.get('path') and old.get('package_status')=='verified':
                for key in ('package_status','package_member','nested_package','nested_sha256'):
                    s[key]=old[key]
        model['package']={**previous['package'],'verified_sources':sum(s['package_status']=='verified' for s in sources.values()),
                          'unmatched_sources':[sid for sid,s in sources.items() if s['origin']=='cann' and s['package_status']!='verified']}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(model,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps(model['coverage'],ensure_ascii=False,indent=2))
    return model


def dialect_navigation(model, dialect):
    ops = {op['id']: op for op in model['ops']}
    edges = []
    for intr in dialect['intrinsics']:
        op = ops.get(identity(intr['llvm_intrinsic']))
        if op is None:
            continue
        edges.append({'from':intr['id'],'to':op['id'],'kind':'exact_llvm_symbol','basis':intr['source']})
        for upper in intr['upstream_op_ids']:
            edges.append({'from':upper,'to':op['id'],'kind':'dialect_mapping','via':intr['id']})
        for builtin in intr['ccec_candidate_op_ids']:
            edges.append({'from':builtin,'to':op['id'],'kind':'naming_candidate','via':intr['id']})
    return edges


def generator_digest():
    return hashlib.sha256(b''.join((ROOT/'scripts'/name).read_bytes() for name in ('llvm_ir.py','llvm_sources.py','llvm_calls.py','llvm_a5.py'))).hexdigest()


def web_payload(model):
    """Losslessly pack repeated field names; reconstruct ordinary records in the browser."""
    payload = dict(model)
    payload['web_encoding'] = 'columnar-v1'
    keys = sorted({k for op in model['ops'] for k in op['presence']})
    payload['presence_columns'] = keys
    records = [{**o,'presence':[['not_scanned','scanned_absent','observed'].index(o['presence'].get(k,'not_scanned')) for k in keys]} for o in model['ops']]
    for name, rows in [('ops',records),('forms',model['forms'])]:
        columns = sorted({key for row in rows for key in row})
        payload[name] = {'columns':columns,'rows':[[row.get(key) for key in columns] for row in rows]}
    return payload


def coverage(model):
    ops=model['ops']; target=[o for o in ops if o['domain']=='target_intrinsic']
    a={o['name'] for o in target if o['presence'].get('hivmc_a5')=='observed'}
    b={o['name'] for o in target if any(o['presence'].get(k)=='observed' for k in ('ccec','llc'))}
    return {'records':len(ops),'domains':dict(Counter(o['domain'] for o in ops)),
            'identities':dict(Counter(o['identity_status'] for o in ops)),
            'default_a5_source_view':sum(o['a5_source_lead'] and o['identity_status']!='candidate_only' for o in ops),
            'default_a5_evidence_view':sum(default_visible(o) for o in ops),
            'forms':len(model['forms']),'form_kinds':dict(Counter(f['kind'] for f in model['forms'])),
            'unparsed_registry_types':sum(f.get('status')=='unparsed_vendor_encoding' for f in model['forms']),
            'partial_bitcode_signatures':sum(f.get('signature_status')=='partial_vendor_types' for f in model['forms']),
            'target_evidence':dict(Counter(o['target_status'] for o in target)),
            'tool_name_sets':{'hivmc_a5':len(a),'ccec_llc':len(b),'intersection':len(a&b),'a5_only':len(a-b),'ccec_llc_only':len(b-a)},
            'failed_scans':sum(s['status']=='failed' for s in model['scans']),
            'relations':dict(Counter(e['kind'] for e in model['relations']))}


def default_visible(op):
    return op.get('static_target',{}).get('package_evidence',False)


def validate_model(model, check_generator=True):
    errors=[]
    if model.get('schema_version')!='ackb.llvm.index.v1': errors.append('Unsupported LLVM schema')
    if check_generator and model.get('generator_sha256')!=generator_digest(): errors.append('Stale LLVM generator snapshot')
    ids={o['id'] for o in model['ops']}; forms={f['id']:f for f in model['forms']}
    if len(ids)!=len(model['ops']) or len(forms)!=len(model['forms']): errors.append('Duplicate identity')
    if any(s['origin'] != 'cann' for s in model['sources'].values()):
        errors.append('Non-CANN evidence source')
    for op in model['ops']:
        if not op['evidence'] or set(op['presence']) - model['sources'].keys():
            errors.append('Missing or external LLVM evidence')
        if op['a5_source_lead'] != (op['presence'].get('hivmc_a5') == 'observed' or op['target_status'] == 'c310_module_declaration'):
            errors.append('Invalid package A5 scope')
        if op['id']!=identity(op['name'],op['domain']): errors.append('Unstable identity')
        if op['identity_status']=='candidate_only' and op['form_ids']: errors.append('Candidate fabricated signature')
        if op['target_status'] not in ('unknown','c310_module_declaration'): errors.append('Unsupported target conclusion')
        if set(op['verification'].values())!={'unverified'}: errors.append('Unsupported experiment claim')
        for fid in op['form_ids']:
            if fid not in forms or forms[fid]['op_id']!=op['id']: errors.append('Broken form link')
        if op['target_status']=='c310_module_declaration' and not any(e['kind']=='bitcode_declaration' and '.c310.' in model['sources'][e['source_id']]['path'] for e in op['evidence']): errors.append('Missing c310 module evidence')
        for ev in op['evidence']:
            if ev['source_id'] not in model['sources']: errors.append('Missing evidence source')
    for f in forms.values():
        if f['op_id'] not in ids: errors.append('Orphan form')
        if f.get('status')=='unparsed_vendor_encoding' and 'signature' in f: errors.append('Unparsed type invented signature')
        for e in f['evidence']:
            if e['source_id'] not in model['sources']: errors.append('Missing form source')
    for s in model['sources'].values():
        if not re.fullmatch('[0-9a-f]{64}',s['sha256']): errors.append('Invalid source hash')
    for e in model['relations']:
        if e['to'] not in ids: errors.append('Missing relation target')
    if model['coverage']!=coverage(model): errors.append('Coverage mismatch')
    if 'static_target' in model['ops'][0]:
        from llvm_a5 import classify, iter_calls
        by_id={o['id']:o for o in model['ops']}; grouped={}; seen=set()
        for call in iter_calls(model):
            if call['id'] in seen: errors.append('Duplicate A5 call')
            seen.add(call['id']); grouped.setdefault(call['op_id'],Counter())[call['module_core']]+=1
            if call['op_id'] not in by_id or call['callee']!=by_id[call['op_id']]['name']: errors.append('A5 call identity mismatch')
            if '.c310.' not in model['sources'].get(call['source_id'],{}).get('path',''): errors.append('A5 call lacks c310 source')
            for fid in call['form_ids']:
                if fid not in forms or forms[fid]['op_id']!=call['op_id'] or not any(e['source_id']==call['source_id'] and e.get('type_id')==call['function_type_id'] for e in forms[fid]['evidence']): errors.append('A5 call signature mismatch')
        for op in model['ops']:
            if op['static_target']!=classify(op,grouped.get(op['id'],[])): errors.append('A5 classification mismatch')
        summary=model.get('a5_static_summary',{})
        if summary.get('calls')!=len(seen) or summary.get('statuses')!=dict(Counter(o['static_target']['status'] for o in model['ops'])): errors.append('A5 coverage mismatch')
        mapping=model.get('target_mapping',{})
        if mapping.get('chip')!=model['target'] or mapping.get('npu_arch')!=3510 or mapping.get('version_fields',{}).get('ccec_aic_version')!='dav-c310-cube' or mapping.get('version_fields',{}).get('ccec_aiv_version')!='dav-c310-vec': errors.append('A5 target mapping mismatch')
    return sorted(set(errors))


def verify_package(model, package, work_dir):
    from verify_package import archive_stream
    catalog=json.loads((ROOT/'data'/VERSION/'catalog.json').read_text())
    digest=file_digest(package)
    if digest!=catalog['source']['package_sha256']: raise ValueError('Wrong pinned package')
    names={'cann-bisheng-compiler_9.3.0_linux-x86_64.run','ascendnpu-ir_2.0.0_linux-x86.run'}
    work_dir.mkdir(parents=True,exist_ok=True)
    nested={}
    with archive_stream(package) as stream, tarfile.open(fileobj=stream,mode='r|*') as archive:
        for member in archive:
            name=Path(member.name).name
            if name in names and member.isfile():
                p=work_dir/name
                with p.open('wb') as out: shutil.copyfileobj(archive.extractfile(member),out)
                nested[name]=p
    verified={}
    for name,p in nested.items():
        nh=file_digest(p)
        with archive_stream(p) as stream, tarfile.open(fileobj=stream,mode='r|*') as archive:
            for member in archive:
                path=member.name.removeprefix('./')
                matches=[s for s in model['sources'].values() if s['origin']=='cann' and (path==s['path'] or path.endswith('/'+s['path']) or path==s['path'].removeprefix('tools/'))]
                if not member.isfile() or not matches: continue
                h=hashlib.sha256()
                stream_file=archive.extractfile(member)
                for block in iter(lambda:stream_file.read(1024*1024),b''):h.update(block)
                for s in matches:
                    if h.hexdigest()!=s['sha256']: raise ValueError('Package mismatch: '+s['path'])
                    s.update(package_status='verified',package_member=path,nested_package=name,nested_sha256=nh)
                    verified[s['id']]=path
    model['package']={'name':package.name,'sha256':digest,'verified_sources':len(verified),
                      'unmatched_sources':[s['id'] for s in model['sources'].values() if s['origin']=='cann' and s['id'] not in verified]}
    return model


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=['extract','validate','verify-package'])
    p.add_argument('--toolkit',type=Path);p.add_argument('--repo',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--output',type=Path,default=OUTPUT);p.add_argument('--package',type=Path);p.add_argument('--work-dir',type=Path)
    a=p.parse_args()
    if a.command=='extract': extract(a.toolkit,a.output)
    else:
        m=json.loads(a.output.read_text())
        if a.command=='verify-package':
            verify_package(m,a.package,a.work_dir);a.output.write_text(json.dumps(m,ensure_ascii=False,separators=(',',':'))+'\n');print(m['package'])
        errors=validate_model(m)
        if errors: raise ValueError('; '.join(errors))
        print('LLVM index valid')


if __name__=='__main__':main()
