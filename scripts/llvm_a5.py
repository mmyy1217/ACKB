"""Attach per-form, module-specific A5 static evidence without support inference."""
import configparser
import hashlib
import json
from collections import Counter
from pathlib import Path
from llvm_calls import direct_calls


def classify(op, calls):
    call_count=sum(calls.values()) if isinstance(calls,Counter) else len(calls)
    cores=sorted(calls) if isinstance(calls,Counter) else sorted({c['module_core'] for c in calls})
    declarations=[e for e in op['evidence'] if e['kind']=='bitcode_declaration' and e['source_id'].startswith('bc_meta_op_') and '_c310_' in e['source_id']]
    if op['domain']=='ordinary_ir':status='reference_model'
    elif call_count:status='c310_direct_call'
    elif declarations:status='c310_declaration'
    elif op['presence'].get('hivmc_a5')=='observed':status='a5_name_only'
    elif op['identity_status']=='lowering_reference':status='external_only'
    elif op['identity_status']=='registered':status='cross_arch_registry'
    else:status='insufficient'
    return {'status':status,'package_evidence':bool(declarations),'call_count':call_count,
            'module_cores':cores,
            'support':'not_established','exclusion':'not_established'}


def enrich(model, toolkit):
    toolkit=Path(toolkit)
    relative='x86_64-linux/data/platform_config/Ascend950PR_9579.ini'
    p=toolkit/relative
    cfg=configparser.ConfigParser();cfg.read(p)
    version=dict(cfg['version'])
    if version.get('npuarch')!='3510' or version.get('aic_version')!='AIC-C-310':raise ValueError('Unexpected 950 target mapping')
    model['target_mapping']={'chip':'Ascend950PR_9579','family':'Ascend950','npu_arch':3510,'aic_version':'AIC-C-310',
        'source':relative,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'package_status':'not_verified',
        'scope':'This exact configuration; not every A5 product','version_fields':version}
    by_name={o['name']:o for o in model['ops']}
    forms={f['id']:f for f in model['forms']}
    all_calls=[];scans=[]
    for sid,source in model['sources'].items():
        if '.c310.' not in source['path'] or not source['path'].endswith('.bc'):continue
        p=toolkit/source['path'];raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Changed bitcode source: '+source['path'])
        print('Scan calls: '+p.name,flush=True)
        try:r=direct_calls(raw)
        except (ValueError,IndexError,StopIteration) as error:
            scans.append({'source_id':sid,'status':'failed','error':str(error)});continue
        source['module']['body_analysis']='direct_calls_partial' if r['issues'] else 'direct_calls_complete'
        core=p.name.split('.c310.')[0].removeprefix('meta_op.')
        matched=0
        for c in r['calls']:
            op=by_name.get(c['callee'])
            if not op:continue
            fids=[fid for fid in op['form_ids'] if any(e['source_id']==sid and e.get('type_id')==c['function_type_id'] for e in forms[fid]['evidence'])]
            if not fids:raise ValueError('Call without matching module signature: '+c['callee'])
            cid='llvm_call_'+hashlib.sha256(f'{sid}:{c["bit_offset"]}'.encode()).hexdigest()[:20]
            all_calls.append({'id':cid,'op_id':op['id'],'source_id':sid,'module_core':core,'form_ids':fids,**c});matched+=1
        scans.append({'source_id':sid,'status':'partial' if r['issues'] else 'complete','bodies':r['bodies'],'direct_calls':len(r['calls']),
            'intrinsic_calls':matched,'issues':r['issues'],'issue_counts':r['issue_counts']})
    grouped={}
    for c in all_calls:grouped.setdefault(c['op_id'],[]).append(c)
    for op in model['ops']:op['static_target']=classify(op,grouped.get(op['id'],[]))
    model['a5_call_table']=pack_calls(all_calls);model['a5_call_scans']=scans
    audit=literal_audit(toolkit)
    model['a5_static_summary']={'statuses':dict(Counter(o['static_target']['status'] for o in model['ops'])),
        'calls':len(all_calls),'modules':len(scans),'failed_modules':sum(s['status']=='failed' for s in scans),
        'unresolved_calls_or_bodies':sum(len(s.get('issues',[])) for s in scans),
        'architecture_rule_audit':audit}
    return model


def pack_calls(calls):
    callers=sorted({c['caller'] for c in calls}); sources=sorted({c['source_id'] for c in calls})
    forms=sorted({fid for c in calls for fid in c['form_ids']})
    ci={x:i for i,x in enumerate(callers)};si={x:i for i,x in enumerate(sources)};fi={x:i for i,x in enumerate(forms)}
    rows=[]
    for c in calls:
        if len(c['form_ids'])!=1:raise ValueError('Ambiguous call signature')
        rows.append([ci[c['caller']],fi[c['form_ids'][0]],si[c['source_id']],c['bit_offset']])
    return {'encoding':'dictionary-v1','columns':['caller','form','source','bit_offset'],'callers':callers,'forms':forms,'sources':sources,'rows':rows}


def iter_calls(model, op_id=None):
    table=model.get('a5_call_table',{'rows':[]});forms={f['id']:f for f in model['forms']};ops={o['id']:o for o in model['ops']}
    for caller,form,source,offset in table['rows']:
        f=forms[table['forms'][form]]
        if op_id and f['op_id']!=op_id:continue
        sid=table['sources'][source];e=next(e for e in f['evidence'] if e['source_id']==sid)
        yield {'id':'llvm_call_'+hashlib.sha256(f'{sid}:{offset}'.encode()).hexdigest()[:20], 'op_id':f['op_id'], 'callee':ops[f['op_id']]['name'],
            'source_id':sid,'caller':table['callers'][caller],'form_ids':[f['id']],'function_type_id':e['type_id'],
            'argument_count':len(f['parameters']),'bit_offset':offset,'module_core':model['sources'][sid]['path'].split('/')[-1].split('.c310.')[0].removeprefix('meta_op.')}


def literal_audit(toolkit):
    digest=hashlib.sha256();count=0;matches=[]
    for root in ('tools/bishengir','tools/bisheng_compiler'):
        for path in sorted((toolkit/root).rglob('*')):
            if not path.is_file() or path.suffix not in ('.h','.hpp','.td','.cpp','.json','.ini'):continue
            raw=path.read_bytes();relative=path.relative_to(toolkit).as_posix();sha=hashlib.sha256(raw).hexdigest()
            digest.update((relative+'\0'+sha+'\n').encode());count+=1
            for line,text in enumerate(raw.decode(errors='replace').splitlines(),1):
                if 'llvm.hivm.' in text or 'llvm.cce.' in text:matches.append({'path':relative,'sha256':sha,'line':line,'excerpt':text.strip()[:300]})
    return {'method':'literal LLVM names in h/hpp/td/cpp/json/ini; dynamic names and binary implementation not resolved',
        'files_scanned':count,'manifest_sha256':digest.hexdigest(),'matches':matches,
        'conclusion':'词法命中仅作线索；未从中建立逐项架构支持或排除规则。外部 Dialect 和候选 builtin 关系不传递目标支持。'}
