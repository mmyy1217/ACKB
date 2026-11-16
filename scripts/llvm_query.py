"""Bounded AI queries over normalized LLVM evidence."""
import json
from pathlib import Path
from catalog import ROOT, file_digest
from llvm_ir import OUTPUT, PROTOCOL, validate_model, default_visible


def dispatch(args, page):
    path=Path(args.data) if args.data else OUTPUT
    if path.is_dir(): path=path/'index.json'
    model=json.loads(path.read_text())
    errors=validate_model(model)
    if errors: raise ValueError('; '.join(errors))
    if args.command=='schema': return json.loads((ROOT/'schemas/llvm-ir-v1.schema.json').read_text())
    context={'schema_version':PROTOCOL,'backend':'llvm','operation':args.command,'version':model['version'],
             'target':model['target'],'index_sha256':file_digest(path),'limitations':model['limitations']}
    ops={o['id']:o for o in model['ops']}; forms={f['id']:f for f in model['forms']}
    identity=getattr(args,'identity','')
    def evidence(items):
        return [{**e,'source':model['sources'][e['source_id']]} for e in items]
    def brief(o):
        return {k:o[k] for k in ('id','name','domain','family','identity_status','target_status','a5_source_lead','form_ids')}
    if args.command=='info':
        items=[{'coverage':model['coverage'],'package':model.get('package'), 'scans':model['scans'],
                'sources':model['sources'],'verification':{'compile':'unverified','runtime':'unverified','performance':'unverified'}}]
    elif args.command in ('get','forms','evidence','relations'):
        op=ops.get(identity)
        if not op: raise ValueError('Unknown LLVM identity: '+identity)
        if args.command=='get':
            items=[{k:v for k,v in op.items() if k!='evidence'}]
            items[0].update(evidence_query={'operation':'evidence','identity':identity},relations_query={'operation':'relations','identity':identity},forms_query={'operation':'forms','identity':identity})
        elif args.command=='forms':
            items=[{**forms[fid],'evidence':evidence(forms[fid]['evidence'])} for fid in op['form_ids']]
        elif args.command=='evidence': items=evidence(op['evidence'])
        else: items=[e for e in model['relations'] if identity in (e['from'],e['to'])]
    elif args.command=='search':
        for field in ('chip','architecture','core','condition','support','builtin','deprecation'):
            if getattr(args,field,None): raise ValueError('--'+field+' is not an LLVM evidence filter')
        query=(getattr(args,'name',None) or args.query or '').lower()
        scope=args.scope
        items=[]
        for op in model['ops']:
            if scope=='a5-sources' and not (op['a5_source_lead'] or op['domain']=='ordinary_ir'): continue
            if not args.include_candidates and op['identity_status']=='candidate_only': continue
            if args.domain and op['domain']!=args.domain: continue
            if args.source and op['presence'].get(args.source)!='observed': continue
            if args.evidence_kind and not any(e['kind']==args.evidence_kind for e in op['evidence']): continue
            if query not in op['name'].lower(): continue
            if args.signature and not any(args.signature.lower() in forms[f].get('signature','').lower() for f in op['form_ids']): continue
            items.append(brief(op))
        context['filters']={'scope':scope,'include_candidates':args.include_candidates,'domain':args.domain,'source':args.source,'evidence_kind':args.evidence_kind}
    elif args.command=='gaps':
        linked={e['to'] for e in model['relations'] if e['from'].startswith('ccec_op_')}
        items=[]
        for op in model['ops']:
            if op['domain']!='target_intrinsic': continue
            reasons=[]
            if op['id'] not in linked: reasons.append('no_ccec_mapping_in_index')
            if not any(forms[f].get('signature') for f in op['form_ids']): reasons.append('no_readable_signature')
            if op['target_status']=='unknown': reasons.append('no_c310_declaration_evidence')
            if op['presence'].get('hivmc_a5')=='observed' and all(op['presence'].get(k)!='observed' for k in ('ccec','llc')): reasons.append('hivmc_a5_only_name')
            if reasons and (not args.gap or args.gap in reasons): items.append({**brief(op),'gaps':reasons})
    else: raise ValueError('Unsupported LLVM query: '+args.command)
    return page(items,args,context)
