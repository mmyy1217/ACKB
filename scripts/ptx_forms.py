"""Extract concrete PTX spellings with bounded, explicitly audited grammar expansion."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
from nvvm_index import Reader, ROOT

class PTXReader(Reader):
    def __init__(self):
        super().__init__();self.rubric='';self.rubric_text=None
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        if tag=='section':self.rubric=''
        if tag=='p' and 'rubric' in dict(attrs).get('class','').split():self.rubric_text=[]
    def handle_data(self,text):
        super().handle_data(text)
        if self.rubric_text is not None:self.rubric_text.append(text)
    def handle_endtag(self,tag):
        if tag=='p' and self.rubric_text is not None:self.rubric=''.join(self.rubric_text);self.rubric_text=None
        if tag=='pre' and not self.rubric.startswith('Example'):self.pre=None
        super().handle_endtag(tag)

OUTPUT=ROOT/'data/ptx/forms.json'
# These syntax families have independent mnemonic qualifiers; operand constraints
# remain attached to the original syntax and are not inferred by this extractor.
SAFE={'add','sub','mul','mad','mul24','mad24','sad','div','rem','abs','neg','min','max','popc','clz','bfind','fns','brev','bfe','bfi','szext','bmsk','addc','subc','madc','and','or','xor','not','cnot','shl','shr'}

def expand(text):
    enums={}
    for m in re.finditer(r'((?:\.\w+\s*=\s*)+)\{([^{}]+)\}\s*;',text):
        values=re.findall(r'\.[A-Za-z0-9_]+',m[2])
        for key in re.findall(r'\.(\w+)\s*=',m[1]): enums[key]=values
    found=set()
    for line in text.splitlines():
        m=re.match(r'^\s*([a-z][\w.]*(?:\{[^{}]+\}[\w.]*)*)\s+[^=]+;',line)
        if not m:continue
        token=m[1]
        if token.split('.')[0].split('{')[0] not in SAFE:continue
        options=[token]
        while any('{' in x for x in options):
            out=[]
            for x in options:
                hit=re.search(r'\{([^{}]+)\}',x)
                if hit:
                    out.extend([x[:hit.start()]+v+x[hit.end():] for v in ['',hit[1]]])
                else:out.append(x)
            options=out
        for x in options:
            parts=x.split('.'); choices=[[parts[0]]]+[[v.lstrip('.') for v in enums[p]] if p in enums else [p] for p in parts[1:]]
            for seq in itertools.product(*choices):
                if any(p in {'type','dtype','stype','mode','rnd','shape','vec'} or re.fullmatch(r'(?:[abcds]?type|rnd|mode)\d*',p) for p in seq):continue
                name='.'.join(seq)
                # wide multiplication is undefined for 64-bit operands.
                if '.wide.' in name and name.endswith(('u64','s64')):continue
                found.add(name)
    return sorted(found)

def extract(path):
    raw=path.read_bytes();syntax=json.loads((ROOT/'data/ptx/syntax.json').read_text());assert hashlib.sha256(raw).hexdigest()==syntax['source_sha256']
    instructions=json.loads((ROOT/'data/ptx/instructions.json').read_text());anchors={x['anchor']:x for x in instructions}
    reader=PTXReader();reader.feed(raw.decode());forms={}; unresolved=[]
    def add(anchor,name,kind):
        key=anchor+'|'+name
        f=forms.setdefault(key,{'id':'ptx_form_'+hashlib.sha256(key.encode()).hexdigest()[:20],'anchor':anchor,'name':name,'evidence':[]})
        if kind not in f['evidence']:f['evidence'].append(kind)
    for a,item in anchors.items():
        txt=syntax['entries'].get(a,{}).get('text','')
        if a.startswith(('integer-arithmetic-instructions-','extended-precision-arithmetic-instructions-','floating-point-instructions-')):
            for name in expand(txt):add(a,name,'audited_syntax_expansion')
    for a,title,line,block in reader.blocks:
        if a not in anchors:continue
        roots={m.split('.')[0] for m in anchors[a]['mnemonics']}
        for token in re.findall(r'(?m)^\s*(?:@!?%?\w+\s+)?([a-z][\w]*(?:\.[A-Za-z0-9_:]+)+)\s+[^\n;]*;',block):
            if token.split('.')[0] not in roots:continue
            if re.search(r'\.(?:type\d*|dtype|stype|rnd|mode|shape|ss|scope|sem|op|kind|vec)(?:\.|$)',token):continue
            add(a,token,'literal_official_code')
    for a,item in anchors.items():
        subset=[f for f in forms.values() if f['anchor']==a]
        unresolved.append({'anchor':a,'coverage':'bounded_forms_not_exhaustive','forms':len(subset)})
        if not subset:
            for name in item['mnemonics']:add(a,name,'unexpanded_instruction_entry')
    return {'schema_version':'ackb.ptx.forms.v1','source_sha256':syntax['source_sha256'],'forms':sorted(forms.values(),key=lambda f:(f['name'],f['anchor'])),'coverage':unresolved,'limitations':['完整形式来自官方代码与有界语法展开；复杂约束未宣称穷举。','指令条目支持条件不自动成为每个具体形式的支持证明。','没有具体形式的条目保留原名；完整官方语法始终可查。']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--html',type=Path,required=True);a=p.parse_args();d=extract(a.html);OUTPUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(len(d['forms']))
