"""Index literal NVVM symbols from a pinned official specification, without execution."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/nvvm/index.json'
URL = 'https://docs.nvidia.com/cuda/archive/13.4.3/nvvm-ir-spec/index.html'

class Reader(HTMLParser):
    def __init__(self):
        super().__init__(); self.anchor=''; self.title=''; self.heading=None; self.pre=None; self.blocks=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='section': self.anchor=a.get('id',self.anchor)
        if tag in ('h1','h2','h3','h4'): self.heading=[]
        if tag=='pre': self.pre=[]; self.start=self.getpos()[0]
    def handle_data(self, text):
        if self.heading is not None: self.heading.append(text)
        if self.pre is not None: self.pre.append(text)
    def handle_endtag(self, tag):
        if tag in ('h1','h2','h3','h4') and self.heading is not None:
            self.title=''.join(self.heading).replace('','').strip(); self.heading=None
        if tag=='pre' and self.pre is not None:
            self.blocks.append((self.anchor,self.title,self.start,''.join(self.pre))); self.pre=None

def extract(path):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '102a5a7c531d65bb0b99cf2fdb28060680489265bc1b95edb9ddc6458adfaa97':
        raise ValueError('NVVM source differs from the pinned 13.4.3 snapshot')
    parser=Reader(); parser.feed(raw.decode()); rows={}
    pattern=r'\bllvm\.[A-Za-z_][A-Za-z_0-9.<>]*(?=\s*\()'
    for anchor,title,line,block in parser.blocks:
        for name in sorted(set(re.findall(pattern,block))):
            if name.endswith('.') or name in ('llvm.nvvm','llvm.dbg','llvm.module.flags'): continue
            item=rows.setdefault(name,{'id':'nvvm_'+hashlib.sha256(name.encode()).hexdigest()[:20], 'name':name,'family':title,'evidence':[],'signatures':[], 'support':'unknown','name_kind':'template' if '<' in name else 'literal'})
            item['evidence'].append({'anchor':anchor,'line':line,'kind':'specification_code'})
            for source_line in block.splitlines():
                if re.search(re.escape(name)+r'\s*\(',source_line) and source_line.strip() not in item['signatures']:
                    item['signatures'].append(source_line.strip())
    return {'schema_version':'ackb.nvvm.v1','version':'CUDA 13.4.3 / NVVM IR 2.0','source':{'url':URL,'sha256':hashlib.sha256(raw).hexdigest()},'records':sorted(rows.values(),key=lambda r:r['name']), 'limitations':['固定官方规范代码块中的符号及泛型名称模板索引，不是编译器注册表全集。','符号出现不代表 B300 全部形式可用；目标编译、运行均未验证。','签名保留原文行；泛型占位符不展开为未经文档确认的符号。']}

def validate(d):
    assert d['records'] and len({r['id'] for r in d['records']})==len(d['records'])
    assert len(d['source']['sha256'])==64
    for r in d['records']: assert r['name'].startswith('llvm.') and r['evidence']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['extract','validate']);p.add_argument('--html',type=Path);a=p.parse_args()
    if a.command=='extract':
        d=extract(a.html);validate(d);OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    else: d=json.loads(OUTPUT.read_text());validate(d)
    print(f"NVVM: {len(d['records'])} name records validated")
