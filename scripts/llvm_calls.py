"""Bounded LLVM 15 direct-call reader; unsupported encodings stop a body."""
from collections import Counter
from llvm_sources import Bitstream

VALUE_CODES = {2,3,4,5,6,7,8,9,16,19,20,23,26,27,28,29,30,38,40,41,43,46,47,50,51,52,56,58,59}
VOID_CODES = {1,10,11,12,15,24,31,33,35,36,39,42,44,45,48,49,55,60}


def direct_calls(data):
    calls, issues, functions, types, definitions = [], [], {}, [], []
    body_count = 0
    module_count = None
    def body(records, module, offset):
        nonlocal body_count, module_count
        if module_count is None:
            for b,c,v,_,pos in module:
                if b==17 and c not in (1,19): types.append((c,v))
                if b==8 and c in (7,8,9,14,18):
                    idx=len(functions)
                    functions[idx]={'record':v,'function':c==8,'offset':pos}
                    if c==8 and not v[4]: definitions.append(idx)
            module_count=len(functions)+sum(b==11 and c!=1 for b,c,*_ in module)
        if body_count>=len(definitions): raise ValueError('Function body lacks definition')
        caller=definitions[body_count];body_count+=1
        tid=functions[caller]['record'][2]
        if types[tid][0]==8:tid=types[tid][1][0]
        if types[tid][0]!=21:raise ValueError('Caller type is not a function')
        value=module_count+len(types[tid][1])-2
        staged=[]
        try:
            for b,c,v,_,pos in records:
                if b==11:
                    if c!=1:value+=1
                    continue
                if b!=12:continue
                if c in VALUE_CODES:value+=1
                elif c in VOID_CODES:continue
                elif c==34:
                    flags=v[1];i=2+bool(flags & (1<<17))
                    explicit=bool(flags & (1<<15))
                    fty=v[i] if explicit else None
                    if explicit:i+=1
                    target=(value-v[i]) & 0xffffffff;i+=1
                    if target>=value:i+=1 # Forward references carry a type ID.
                    callee=functions.get(target)
                    if fty is None:
                        if not callee or not callee['function']:raise ValueError('Indirect call without explicit function type')
                        fty=callee['record'][2]
                        if types[fty][0]==8:fty=types[fty][1][0]
                    if fty>=len(types) or types[fty][0]!=21:raise ValueError('Unrecognized call function type')
                    ft=types[fty][1]
                    if len(v)-i<len(ft)-2 or (not ft[0] and len(v)-i!=len(ft)-2):raise ValueError('Call argument count mismatch')
                    if callee and callee['function']:
                        declared=callee['record'][2]
                        if types[declared][0]==8:declared=types[declared][1][0]
                        if declared!=fty:raise ValueError('Direct callee type mismatch')
                        staged.append({'caller_id':caller,'callee_id':target,'bit_offset':pos,'function_type_id':fty,'argument_count':len(ft)-2})
                    else:issues.append({'caller_id':caller,'bit_offset':pos,'reason':'Indirect/constant-expression callee unresolved'})
                    if types[ft[1]][0]!=2:value+=1
                else:raise ValueError(f'Unsupported function record {c}')
        except (ValueError,IndexError) as error:
            issues.append({'caller_id':caller,'bit_offset':pos,'reason':str(error),'body_offset':offset})
            return # Discard the entire body when value numbering is not validated.
        calls.extend(staged)
    records=Bitstream(data,body_handler=body).read()
    strings=next(blob for b,c,_,blob,_ in records if b==23 and c==1)
    version=next(v[0] for b,c,v,_,_ in records if b==8 and c==1)
    if version!=2:raise ValueError('Only relative-ID module version 2 supported')
    if body_count!=len(definitions):raise ValueError('Definition/body count mismatch')
    def name(idx):
        r=functions[idx]['record'];return strings[r[0]:r[0]+r[1]].decode()
    for item in calls:
        item['caller']=name(item.pop('caller_id'));item['callee']=name(item.pop('callee_id'))
    for item in issues:item['caller']=name(item.pop('caller_id'))
    return {'bodies':body_count,'calls':calls,'issues':issues,'issue_counts':dict(Counter(i['reason'] for i in issues))}
