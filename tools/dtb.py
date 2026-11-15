"""Harmonix binary DTA (.dta_dta_ps3 / .moggsong_dta_ps3): read, write, decompile to text, compile from text."""
import struct,sys,re
STR_T={2,5,7,0x12,0x20,0x21,0x22,0x23,0x24,0x25}; ARR_T={0x10:'()',0x11:'{}',0x13:'[]'}
def read(b):
    def node(p):
        line,cnt,nid=struct.unpack_from('<IHH',b,p); p+=8; kids=[]
        for _ in range(cnt):
            t=struct.unpack_from('<I',b,p)[0]; p+=4
            if t in ARR_T: v,p=node(p)
            elif t in STR_T:
                l=struct.unpack_from('<I',b,p)[0]; v=b[p+4:p+4+l]; p+=4+l
            else: v=b[p:p+4]; p+=4
            kids.append((t,v))
        return {'line':line,'id':nid,'kids':kids},p
    assert b[0]==1; tree,p=node(1); return tree
def write(tree):
    out=[b'\x01']
    def node(n):
        out.append(struct.pack('<IHH',n['line'],len(n['kids']),n['id']))
        for t,v in n['kids']:
            out.append(struct.pack('<I',t))
            if t in ARR_T: node(v)
            elif t in STR_T: out.append(struct.pack('<I',len(v))+v)
            else: out.append(v)
    node(tree); return b''.join(out)
if __name__=='__main__':
    t=read(open(sys.argv[1],'rb').read())
    ids=[]
    def walk(n,d):
        ids.append((n['id'],n['line'],d))
        for k,v in n['kids']:
            if k in ARR_T: walk(v,d+1)
    walk(t,0); print(ids[:25])

# ---------- text -> tree ----------
TOK=re.compile(r'''\s+|;[^\n]*|"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|([(){}\[\]])|([^\s(){}\[\];"']+)''',re.S)
DIRECT={'#include':0x21,'#merge':0x22,'#ifdef':0x07,'#ifndef':0x23,'#define':0x20,'#autorun':0x24,'#undef':0x25}
def parse_text(src):
    pos=0; line=1; stack=[{'line':1,'id':1,'kids':[]}]; closers={')':0x10,'}':0x11,']':0x13}; openers={'(':0x10,'{':0x11,'[':0x13}
    pending=None
    while pos<len(src):
        m=TOK.match(src,pos)
        if not m: raise ValueError('bad token at line %d: %r'%(line,src[pos:pos+20]))
        tok=m.group(0); start_line=line; line+=tok.count('\n'); pos=m.end()
        if tok.isspace() or tok.startswith(';'): continue
        cur=stack[-1]['kids']
        if m.group(1) is not None:
            v=re.sub(r'\\(.)',lambda e:{'n':'\n','q':'"'}.get(e.group(1),e.group(1)),m.group(1))
            cur.append((0x12,v.encode('latin-1'))); continue
        if m.group(2) is not None: cur.append((5,m.group(2).encode('latin-1'))); continue
        if m.group(3):
            c=m.group(3)
            if c in openers:
                n={'line':1,'id':start_line,'kids':[],'t':openers[c]}; cur.append((openers[c],n)); stack.append(n)
            else:
                stack.pop()
            continue
        w=m.group(4)
        if pending is not None:
            cur.append((pending,w.encode('latin-1'))); pending=None; continue
        if w in DIRECT: pending=DIRECT[w]; continue
        if w=='#else': cur.append((8,b'\0\0\0\0')); continue
        if w=='#endif': cur.append((9,b'\0\0\0\0')); continue
        if w.startswith('$'): cur.append((2,w[1:].encode('latin-1'))); continue
        if re.fullmatch(r'[-+]?\d+',w): cur.append((0,struct.pack('<i',int(w)))); continue
        if re.fullmatch(r'[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?',w): cur.append((1,struct.pack('<f',float(w)))); continue
        cur.append((5,w.encode('latin-1')))
    def strip(n):
        n.pop('t',None)
        for t,v in n['kids']:
            if t in ARR_T: strip(v)
    strip(stack[0]); return stack[0]
def compile_text(src): return write(parse_text(src))
