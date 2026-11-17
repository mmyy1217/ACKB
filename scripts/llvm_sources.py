"""Bounded, read-only ELF metadata and LLVM bitstream readers (no code execution)."""
import struct


class ELF:
    def __init__(self, data):
        self.data = data
        if data[:6] != b'\x7fELF\x02\x01':
            raise ValueError('Expected ELF64 little endian')
        shoff = struct.unpack_from('<Q', data, 40)[0]
        size, count = struct.unpack_from('<HH', data, 58)
        if size != 64 or not count:
            raise ValueError('Unsupported ELF section headers')
        self.sections = [struct.unpack_from('<IIQQQQIIQQ', data, shoff+i*size) for i in range(count)]
        self.symbols = {}
        for s in self.sections:
            if s[1] != 2:
                continue
            strings = self.section(self.sections[s[6]])
            for off in range(s[4], s[4]+s[5], s[9]):
                name, _, _, _, address, length = struct.unpack_from('<IBBHQQ', data, off)
                label = strings[name:strings.index(b'\0', name)].decode()
                self.symbols[label] = (address, length)
        self.relocations = {}
        for s in self.sections:
            if s[1] == 4:
                for off in range(s[4], s[4]+s[5], s[9]):
                    address, info, addend = struct.unpack_from('<QQq', data, off)
                    if info & 0xffffffff == 8:
                        self.relocations[address] = addend

    def section(self, s):
        return self.data[s[4]:s[4]+s[5]]

    def offset(self, address):
        for s in self.sections:
            if s[1] != 8 and s[3] <= address < s[3]+s[5]:
                return s[4]+address-s[3]
        raise ValueError(f'Unmapped ELF address {address:x}')

    def symbol(self, suffix):
        matches = [(n, v) for n, v in self.symbols.items() if suffix in n]
        if len(matches) != 1:
            raise ValueError(f'Ambiguous/missing metadata symbol {suffix}: {len(matches)}')
        name, (address, size) = matches[0]
        off = self.offset(address)
        return name, address, off, self.data[off:off+size]

    def registry(self):
        _, address, off, table = self.symbol('IntrinsicNameTable')
        _, _, ioff, types = self.symbol('L9IIT_Table')
        _, _, loff, long_types = self.symbol('IIT_LongEncodingTable')
        _, _, _, overloaded = self.symbol('OTable')
        if len(table)//8 != len(types)//4:
            raise ValueError('Intrinsic name/type table length mismatch')
        if struct.unpack_from('<I', types, len(types)-4)[0] != 0:
            raise ValueError('Missing IIT table sentinel')
        records = []
        for index in range(len(table)//8):
            pointer = self.relocations.get(address+index*8, struct.unpack_from('<Q', table, index*8)[0])
            start = self.offset(pointer)
            end = self.data.index(b'\0', start)
            name = self.data[start:end].decode()
            if index == 0 and name == 'not_intrinsic':
                continue
            if index == 0:
                raise ValueError('Missing intrinsic name sentinel')
            if not name.startswith('llvm.') or end-start > 512:
                raise ValueError(f'Invalid registry name at slot {index}: {name}')
            iid = index
            word = struct.unpack_from('<I', types, (iid-1)*4)[0]
            records.append({'name': name, 'registry_id': iid, 'name_offset': off+index*8,
                            'type_offset': ioff+(iid-1)*4, 'type_word': word,
                            'overloaded': bool(overloaded[iid//8] & (1 << (iid%8)))})
        return records, long_types, loff


class Bitstream:
    """Decode container records, preserving unknown record codes and block boundaries."""
    def __init__(self, data, body_handler=None):
        if data[:4] != b'BC\xc0\xde':
            raise ValueError('Expected raw LLVM bitcode magic')
        self.data, self.pos = data, 32
        self.info, self.records = {}, []
        self.body_handler = body_handler

    def bits(self, n):
        if n < 0 or self.pos+n > len(self.data)*8:
            raise ValueError('Bitstream overrun')
        off, shift = divmod(self.pos, 8)
        self.pos += n
        return (int.from_bytes(self.data[off:(self.pos+7)//8], 'little') >> shift) & ((1 << n)-1)

    def vbr(self, n):
        value, shift = 0, 0
        while True:
            x = self.bits(n)
            value |= (x & ((1 << (n-1))-1)) << shift
            if not x >> (n-1):
                return value
            shift += n-1
            if shift > 128:
                raise ValueError('Invalid VBR')

    def align(self):
        self.pos = (self.pos+31)//32*32

    def abbreviation(self):
        out = []
        for _ in range(self.vbr(5)):
            if self.bits(1):
                out.append(('literal', self.vbr(8)))
            else:
                kind = self.bits(3)
                out.append((kind, self.vbr(5) if kind in (1, 2) else 0))
        return out

    def scalar(self, op):
        kind, n = op
        if kind == 'literal': return n
        if kind == 1: return self.bits(n)
        if kind == 2: return self.vbr(n)
        if kind == 4:
            return ord('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._'[self.bits(6)])
        raise ValueError(f'Invalid scalar abbreviation {op}')

    def block(self, block_id=-1, width=2, end=None, path=()):
        end = len(self.data)*8 if end is None else end
        abbreviations = list(self.info.get(block_id, []))
        info_id = None
        while self.pos < end:
            start = self.pos
            code = self.bits(width)
            if code == 0:
                self.align()
                if self.pos != end:
                    raise ValueError('Block length mismatch')
                return
            if code == 1:
                child, child_width = self.vbr(8), self.vbr(4)
                self.align()
                length = self.bits(32)
                child_end = self.pos + 32*length
                if child_end > end:
                    raise ValueError('Child block exceeds parent')
                # Body/metadata records are outside the declaration extraction scope.
                if child == 12 and self.body_handler:
                    begin = len(self.records)
                    self.block(child, child_width, child_end, path+(child,))
                    self.body_handler(self.records[begin:], self.records[:begin], start)
                    del self.records[begin:]
                elif child in (12, 15, 16, 18, 22):
                    self.pos = child_end
                else:
                    self.block(child, child_width, child_end, path+(child,))
                continue
            if code == 2:
                abbreviation = self.abbreviation()
                if block_id == 0:
                    if info_id is None: raise ValueError('BLOCKINFO missing SETBID')
                    self.info.setdefault(info_id, []).append(abbreviation)
                else:
                    abbreviations.append(abbreviation)
                continue
            blob = None
            if code == 3:
                rec, count = self.vbr(6), self.vbr(6)
                values = [self.vbr(6) for _ in range(count)]
            else:
                spec = abbreviations[code-4]
                values, i = [], 0
                while i < len(spec):
                    kind, n = spec[i]
                    if kind == 3:
                        count = self.vbr(6)
                        i += 1
                        values.extend(self.scalar(spec[i]) for _ in range(count))
                    elif kind == 5:
                        count = self.vbr(6)
                        self.align()
                        blob = self.data[self.pos//8:self.pos//8+count]
                        self.pos += count*8
                        self.align()
                    else:
                        values.append(self.scalar(spec[i]))
                    i += 1
                rec, values = values[0], values[1:]
            if block_id == 0 and rec == 1:
                info_id = values[0]
            self.records.append((block_id, rec, values, blob, start))
        if self.pos != end:
            raise ValueError('Invalid block boundary')

    def read(self):
        self.block()
        return self.records


def bitcode_declarations(data):
    records = Bitstream(data).read()
    strings = next(blob for block, code, _, blob, _ in records if block == 23 and code == 1)
    version = next(v[0] for b, c, v, _, _ in records if b == 8 and c == 1)
    if version != 2:
        raise ValueError(f'Unsupported module version {version}')
    types, pending_name = [], ''
    for b, c, v, _, offset in records:
        if b != 17 or c == 1: continue
        if c == 19:
            pending_name = bytes(v).decode()
            continue
        types.append((c, v, pending_name if c in (6, 20) else ''))
        pending_name = ''
    def ty(i, stack=()):
        if i in stack: return '%' + (types[i][2] or f'type{i}')
        c, v, name = types[i]
        sub = lambda x: ty(x, stack+(i,))
        atoms = {2:'void',3:'float',4:'double',5:'label',10:'half',13:'x86_fp80',14:'fp128',15:'ppc_fp128',16:'metadata',17:'x86_mmx',22:'token',23:'bfloat',24:'x86_amx'}
        if c in atoms: return atoms[c]
        if c == 7: return f'i{v[0]}'
        if c == 25: return 'ptr' + (f' addrspace({v[0]})' if v[0] else '')
        if c == 8: return sub(v[0]) + (f' addrspace({v[1]})' if len(v)>1 and v[1] else '') + '*'
        if c == 11: return f'[{v[0]} x {sub(v[1])}]'
        if c == 12: return '<' + ('vscale x ' if len(v)>2 and v[2] else '') + f'{v[0]} x {sub(v[1])}>'
        if c in (6, 20): return '%' + (name or f'type{i}')
        if c == 18: return ('<{' if v[0] else '{') + ', '.join(sub(x) for x in v[1:]) + ('}>' if v[0] else '}')
        if c == 21: return sub(v[1]) + ' (' + ', '.join([sub(x) for x in v[2:]] + (['...'] if v[0] else [])) + ')'
        return f'UNRESOLVED_TYPE_{i}(code={c}, operands={v})'
    result = []
    for b, c, v, _, offset in records:
        if b != 8 or c != 8: continue
        name = strings[v[0]:v[0]+v[1]].decode()
        if not name.startswith('llvm.'): continue
        tid = v[2]
        if types[tid][0] == 8: tid = types[tid][1][0]
        if types[tid][0] != 21: raise ValueError('Function type missing')
        ft = types[tid][1]
        signature = ty(tid)
        result.append({'name':name, 'return_type':ty(ft[1]), 'parameters':[ty(x) for x in ft[2:]],
                       'vararg':bool(ft[0]), 'signature':ty(tid), 'declaration':bool(v[4]),
                       'signature_status':'partial_vendor_types' if 'UNRESOLVED_TYPE_' in signature else 'parsed',
                       'bit_offset':offset, 'type_id':tid})
    text = lambda code: next((bytes(v).decode() for b,c,v,_,_ in records if b==8 and c==code), '')
    return {'triple':text(2), 'data_layout':text(3), 'module_version':version,
            'type_count':len(types), 'functions':result,
            'body_analysis':'not_scanned', 'unknown_types':[{'type_id':i,'code':c,'operands':v} for i,(c,v,_) in enumerate(types) if c not in set(range(2,26))]}


def decode_iit(word, long_table):
    """LLVM 15 IIT constraints; unknown vendor descriptors fail closed."""
    if word & 0x80000000:
        seq, pos = long_table, word & 0x7fffffff
    else:
        seq, pos = [], 0
        while True:
            seq.append(word & 15)
            word >>= 4
            if not word: break
    start = pos
    def take(default=False):
        nonlocal pos
        if pos == len(seq) and default: return 0
        if pos >= len(seq): raise ValueError('Truncated IIT')
        n = seq[pos]; pos += 1
        return n
    atoms = {0:'void',1:'i1',2:'i8',3:'i16',4:'i32',5:'i64',6:'half',7:'float',8:'double',17:'x86_mmx',18:'token',19:'metadata',20:'{}',29:'...',35:'i128',41:'fp128',48:'bfloat',51:'x86_amx',52:'ppc_fp128',57:'i2',58:'i4'}
    vectors = {9:2,10:4,11:8,12:16,13:32,16:64,28:1,36:512,37:1024,47:128,50:256,53:3}
    structs = {21:2,22:3,23:4,24:5,38:6,39:7,40:8,49:9}
    args = {15:'T',25:'extend',26:'trunc',30:'half_vector',31:'same_vector_width',32:'pointer_to',33:'pointer_to_element',42:'element',44:'subdivide2',45:'subdivide4',46:'integer_vector'}
    def typ(depth=0):
        if depth > 32: raise ValueError('IIT recursion limit')
        code = take()
        if code in atoms: return atoms[code]
        if code in vectors: return f'<{vectors[code]} x {typ(depth+1)}>'
        if code in structs: return '{' + ', '.join(typ(depth+1) for _ in range(structs[code])) + '}'
        if code in (14,27):
            space = take() if code == 27 else 0
            pointee = typ(depth+1)
            return f'ptr(as={space}, element={pointee})'
        if code in args:
            value = take(True)
            if code == 31:
                return f'same_vector_width(arg_info={value}, element={typ(depth+1)})'
            return f'{args[code]}(arg_info={value})'
        if code in (34,56): return f'{"vector_pointer_to_element" if code==34 else "any_pointer_to_element"}(arg={take(True)}, ref={take(True)})'
        if code == 43: return 'scalable ' + typ(depth+1)
        if code == 54: return 'ptr(as=10, element={})'
        if code == 55: return 'ptr(as=20, element=i8)'
        raise ValueError(f'Unknown IIT descriptor {code}')
    try:
        ret = typ()
        params = []
        while pos < len(seq) and seq[pos] != 0:
            if len(params) > 256: raise ValueError('IIT parameter limit')
            params.append(typ())
        return {'status':'decoded_llvm15_constraints', 'return_type':ret, 'parameters':params,
                'signature':ret+' ('+', '.join(params)+')', 'encoding':list(seq[start:pos])}
    except (ValueError,IndexError) as error:
        return {'status':'unparsed_vendor_encoding', 'error':str(error), 'encoding_prefix':list(seq[start:min(start+64,len(seq))])}
