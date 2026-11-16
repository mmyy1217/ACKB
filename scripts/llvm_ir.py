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
    'A5 来源视图只表示 hivmc-a5 名称出现、c310 模块声明或外部 Dialect 映射；不能推断逐项设备支持。',
    'IIT 为按上游 LLVM 15 格式解释的类型约束，保留原编码；未知厂商编码不补造签名。',
    'Bitcode 只解析模块声明和类型，不解析函数体；声明不是调用、编译通过或运行验证。',
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


def extract(toolkit, dialect_repo, output=OUTPUT):
    previous = json.loads(output.read_text()) if output.exists() else {}
    sources, ops, forms, edges, scans = {}, {}, {}, [], []
    def source(key, path, origin='cann'):
        base = toolkit if origin == 'cann' else dialect_repo
        p = base/path
        sources[key] = {'id':key, 'origin':origin, 'path':path, 'sha256':file_digest(p), 'bytes':p.stat().st_size,
                        'package_status':'not_verified' if origin=='cann' else 'not_applicable'}
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
    dialect_path = ROOT/'data/cce_dialect/index.json'
    dialect = json.loads(dialect_path.read_text())
    for path, meta in dialect['source']['files'].items():
        sid = 'dialect_'+hashlib.sha256(path.encode()).hexdigest()[:12]
        p = source(sid,path,'cce_dialect')
        if sources[sid]['sha256'] != meta['sha256']: raise ValueError('Dialect source changed: '+path)
        sources[sid]['commit'] = dialect['source']['commit']
        if p.suffix not in ('.td','.cpp','.h'): continue
        lines = p.read_text().splitlines()
        for i,line in enumerate(lines,1):
            for name in re.findall(r'"(llvm\.(?:hivm|cce)\.[A-Za-z0-9_.]+)"',line):
                op = get(name)
                if op['identity_status']=='candidate_only': op['identity_status']='lowering_reference'
                op['presence']['dialect'] = 'observed'; op['a5_source_lead']=True
                op['evidence'].append({'kind':'lowering_source','source_id':sid,'line':i,'excerpt':line.strip()})
    for intr in dialect['intrinsics']:
        op = get(intr['llvm_intrinsic'])
        op['presence']['dialect']='observed'; op['a5_source_lead']=True
        if op['identity_status']=='candidate_only': op['identity_status']='lowering_reference'
        op['family']=intr['family']
        edges.append({'from':intr['id'],'to':op['id'],'kind':'exact_llvm_symbol','basis':intr['source']})
        for upper in intr['upstream_op_ids']:
            edges.append({'from':upper,'to':op['id'],'kind':'dialect_mapping','via':intr['id']})
        for builtin in intr['ccec_candidate_op_ids']:
            edges.append({'from':builtin,'to':op['id'],'kind':'naming_candidate','via':intr['id']})
    # Registered overloaded base names are kept separate from concrete observed symbols.
    bases = sorted((o for o in ops.values() if o.get('registry',{}).get('overloaded')),key=lambda o:-len(o['name']))
    for op in list(ops.values()):
        if op['identity_status']=='registered': continue
        for base in bases:
            if op['name'].startswith(base['name']+'.'):
                edges.append({'from':op['id'],'to':base['id'],'kind':'overload_name_candidate'})
                break
    ordinary = {
        'load / store':('访存 / 布局','普通 LLVM IR 的 load / store 以指针地址空间区分存储位置；它们不是 llvm.hivm.* 调用。'),
        'add / fadd / mul / fmul':('计算 / 其他','标量或向量算术可用普通 SSA 指令表达；最终选指令仍取决于目标 lowering。'),
        'getelementptr / addrspacecast':('访存 / 布局','getelementptr 计算地址，addrspacecast 表达地址空间转换；合法空间组合须由目标验证。'),
        'atomicrmw / cmpxchg / fence':('原子操作','普通 LLVM IR 表达原子更新与内存顺序；某一目标的支持不能由通用语法推断。'),
        'br / phi / select':('控制 / 寄存器','控制流、SSA 合流与值选择属于普通 IR，不需要每项都有专用目标 intrinsic。'),
        'address spaces':('访存 / 布局','外部 CCEDialect 定义 GM=1、L1=2、L0A=3、L0B=4、L0C=5、UB=6、PRIVATE=9。此映射不自动扩展到其他工具链版本。'),
    }
    for name,(fam,summary) in ordinary.items():
        op=get(name,'ordinary_ir'); op.update(family=fam,identity_status='reference_model',summary=summary)
        op['reference_url']='https://releases.llvm.org/15.0.0/docs/LangRef.html'
        if name=='address spaces':
            op['address_spaces']=dialect['target']['address_spaces']
            op['evidence']=[{'kind':'external_model','source_id':sid} for sid,s in sources.items() if s['origin']=='cce_dialect' and s['path']=='include/Utils/AddressSpaces.td']
    # Absence means only that this exact spelling was absent from that completed scan.
    for op in ops.values():
        for sid in [*TOOLS,'dialect',*[x['source_id'] for x in scans if x['method']=='bitcode_declarations' and x['status']=='complete']]:
            op['presence'].setdefault(sid,'scanned_absent' if op['domain']=='target_intrinsic' or sid.startswith('bc_') else 'not_scanned')
    edges = list({json.dumps(e,sort_keys=True):e for e in edges}.values())
    model = {'schema_version':'ackb.llvm.index.v1','version':VERSION,'target':'Ascend950PR_9579',
             'generator_sha256':generator_digest(),'dialect_index_sha256':file_digest(dialect_path),
             'sources':sources,'ops':sorted(ops.values(),key=lambda o:o['name']),
             'forms':sorted(forms.values(),key=lambda f:f['id']),'relations':sorted(edges,key=lambda e:(e['from'],e['to'],e['kind'])),
             'scans':scans,'limitations':LIMITATIONS,
             'format_reference':{'url':'https://github.com/llvm/llvm-project/blob/llvmorg-15.0.5/llvm/lib/IR/Function.cpp','scope':'IIT interpretation, not vendor support authority'}}
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


def generator_digest():
    return hashlib.sha256(Path(__file__).read_bytes()+(ROOT/'scripts/llvm_sources.py').read_bytes()).hexdigest()


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
            'default_a5_source_view':sum(default_visible(o) for o in ops),
            'forms':len(model['forms']),'form_kinds':dict(Counter(f['kind'] for f in model['forms'])),
            'unparsed_registry_types':sum(f.get('status')=='unparsed_vendor_encoding' for f in model['forms']),
            'partial_bitcode_signatures':sum(f.get('signature_status')=='partial_vendor_types' for f in model['forms']),
            'target_evidence':dict(Counter(o['target_status'] for o in target)),
            'tool_name_sets':{'hivmc_a5':len(a),'ccec_llc':len(b),'intersection':len(a&b),'a5_only':len(a-b),'ccec_llc_only':len(b-a)},
            'failed_scans':sum(s['status']=='failed' for s in model['scans']),
            'relations':dict(Counter(e['kind'] for e in model['relations']))}


def default_visible(op):
    return op['domain']=='ordinary_ir' or (op['a5_source_lead'] and op['identity_status']!='candidate_only')


def validate_model(model, check_generator=True):
    errors=[]
    if model.get('schema_version')!='ackb.llvm.index.v1': errors.append('Unsupported LLVM schema')
    if check_generator and model.get('generator_sha256')!=generator_digest(): errors.append('Stale LLVM generator snapshot')
    if model.get('dialect_index_sha256')!=file_digest(ROOT/'data/cce_dialect/index.json'): errors.append('Stale Dialect linkage')
    ids={o['id'] for o in model['ops']}; forms={f['id']:f for f in model['forms']}
    if len(ids)!=len(model['ops']) or len(forms)!=len(model['forms']): errors.append('Duplicate identity')
    for op in model['ops']:
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
    p.add_argument('--toolkit',type=Path);p.add_argument('--repo',type=Path,default=Path('/home/zuomin/Projects/Compiler/CCEDialect'))
    p.add_argument('--output',type=Path,default=OUTPUT);p.add_argument('--package',type=Path);p.add_argument('--work-dir',type=Path)
    a=p.parse_args()
    if a.command=='extract': extract(a.toolkit,a.repo,a.output)
    else:
        m=json.loads(a.output.read_text())
        if a.command=='verify-package':
            verify_package(m,a.package,a.work_dir);a.output.write_text(json.dumps(m,ensure_ascii=False,separators=(',',':'))+'\n');print(m['package'])
        errors=validate_model(m)
        if errors: raise ValueError('; '.join(errors))
        print('LLVM index valid')


if __name__=='__main__':main()
