"""PS3 ARK v9: encrypted .hdr index + main_ps3_N.ark parts. Read, extract, patch."""
import struct,os,sys,re
def _rnd(k):
    r=(k-((k//0x1F31D)*0x1F31D))*0x41A7-(k//0x1F31D)*0xB14
    return r+0x7FFFFFFF if r<=0 else r
def crypt(data,key):
    """XOR stream used by the .hdr (symmetric). key = signed int32 from the first 4 bytes."""
    out=bytearray(data)
    for i in range(len(out)):
        key=_rnd(key); out[i]^=(key&0xff)^0xff
    return bytes(out)
def decrypt_hdr(enc):
    key=struct.unpack_from('<i',enc,0)[0]; return key,crypt(enc[4:],key)
def encrypt_hdr(plain,key): return struct.pack('<i',key)+crypt(plain,key)
def _lstr(b,p): n=struct.unpack_from('<I',b,p)[0]; return b[p+4:p+4+n].decode('latin-1'),p+4+n
def _wstr(s): b=s.encode('latin-1'); return struct.pack('<I',len(b))+b
def parse(h):
    d={}; p=0
    d['version'],d['unk1']=struct.unpack_from('<II',h,p); p+=8
    d['guid']=h[p:p+16]; p+=16
    d['part_count']=struct.unpack_from('<I',h,p)[0]; p+=4
    n=struct.unpack_from('<I',h,p)[0]; p+=4; d['part_sizes']=list(struct.unpack_from('<%dI'%n,h,p)); p+=4*n
    n=struct.unpack_from('<I',h,p)[0]; p+=4; d['part_names']=[]
    for _ in range(n): s,p=_lstr(h,p); d['part_names'].append(s)
    n=struct.unpack_from('<I',h,p)[0]; p+=4; d['part_unk_a']=list(struct.unpack_from('<%dI'%n,h,p)); p+=4*n
    n=struct.unpack_from('<I',h,p)[0]; p+=4; d['part_unk_b']=list(struct.unpack_from('<%dI'%n,h,p)); p+=4*n
    n=struct.unpack_from('<I',h,p)[0]; p+=4; d['files']=[]
    for _ in range(n):
        off=struct.unpack_from('<Q',h,p)[0]; p+=8; name,p=_lstr(h,p)
        a,size,stamp=struct.unpack_from('<iII',h,p); p+=12
        d['files'].append({'offset':off,'name':name,'link':a,'size':size,'stamp':stamp})
    n=struct.unpack_from('<I',h,p)[0]; p+=4; d['buckets']=list(struct.unpack_from('<%di'%n,h,p)); p+=4*n
    assert p==len(h),(p,len(h)); return d
def build(d):
    o=[struct.pack('<II',d['version'],d['unk1']),d['guid'],struct.pack('<I',d['part_count'])]
    o.append(struct.pack('<I%dI'%len(d['part_sizes']),len(d['part_sizes']),*d['part_sizes']))
    o.append(struct.pack('<I',len(d['part_names']))+b''.join(_wstr(s) for s in d['part_names']))
    for k in('part_unk_a','part_unk_b'): o.append(struct.pack('<I%dI'%len(d[k]),len(d[k]),*d[k]))
    o.append(struct.pack('<I',len(d['files'])))
    for f in d['files']: o.append(struct.pack('<Q',f['offset'])+_wstr(f['name'])+struct.pack('<iII',f['link'],f['size'],f['stamp']))
    o.append(struct.pack('<I%di'%len(d['buckets']),len(d['buckets']),*d['buckets']))
    return b''.join(o)
def load(usrdir):
    enc=open(os.path.join(usrdir,'main_ps3.hdr'),'rb').read(); key,h=decrypt_hdr(enc); return key,parse(h)
def read_file(usrdir,d,f):
    starts=[];acc=0
    for s in d['part_sizes']: starts.append(acc); acc+=s
    off=f['offset']; size=f['size']; buf=b''
    for i,st in enumerate(starts):
        if st<=off<st+d['part_sizes'][i]:
            while size>0:
                with open(os.path.join(usrdir,d['part_names'][i]),'rb') as fh:
                    fh.seek(off-starts[i]); c=fh.read(min(size,d['part_sizes'][i]-(off-starts[i])))
                buf+=c; size-=len(c); off+=len(c); i+=1
            return buf
    return b''
NEW_STAMP=0x7D401F60   # stamp on every shipped non-empty entry; empty entries carry 0
def hash_name(name,n):
    """Bucket of a path: h=(h*0x7F+c)%n per character, n = entry count (matches all 1534 shipped entries)."""
    h=0
    for c in name.encode('latin-1'): h=(h*0x7F+c)%n
    return h
def rebuild_table(files):
    """Set every entry's link and return the bucket heads. A later entry heads its chain; -1 ends a chain."""
    n=len(files); heads=[-1]*n
    for i,f in enumerate(files):
        b=hash_name(f['name'],n); f['link']=heads[b]; heads[b]=i
    return heads
def find(d,name):
    """Index of `name` found through the bucket table and link chain the way the game looks it up, or -1."""
    n=len(d['buckets'])
    if not n: return -1
    i=d['buckets'][hash_name(name,n)]
    while i!=-1 and d['files'][i]['name']!=name: i=d['files'][i]['link']
    return i
def patch(usrdir,outdir,replacements,part_name=None):
    """Write a new part with replacement and new files and a new hdr to outdir. Original parts are never modified.
    replacements: {archive_path: bytes}. A path the archive lacks is appended as a new entry, then the bucket
    table and links are rebuilt for the new entry count. With no new path the table stays as shipped."""
    key,d=load(usrdir); idx={f['name']:f for f in d['files']}
    new=[k for k in replacements if k not in idx]
    bad=[k for k in new if not re.fullmatch(r'ps3/[a-z0-9_./-]+',k) or '//' in k]
    if bad: raise ValueError('new archive paths must be lowercase ps3/... names: %s'%bad)
    part_name=part_name or 'main_ps3_%d.ark'%len(d['part_names'])
    base=sum(d['part_sizes']); blob=bytearray()
    for name,data in replacements.items():
        if name in idx: f=idx[name]
        else: f={'offset':0,'name':name,'link':-1,'size':0,'stamp':NEW_STAMP if data else 0}; d['files'].append(f)
        f['offset']=base+len(blob); f['size']=len(data); blob+=data
    if new: d['buckets']=rebuild_table(d['files'])
    d['part_count']+=1; d['part_sizes'].append(len(blob)); d['part_names'].append(part_name)
    d['part_unk_a'].append(0); d['part_unk_b'].append(0)
    os.makedirs(outdir,exist_ok=True)
    open(os.path.join(outdir,part_name),'wb').write(blob)
    open(os.path.join(outdir,'main_ps3.hdr'),'wb').write(encrypt_hdr(build(d),key))
    return part_name,len(blob)
if __name__=='__main__':
    if sys.argv[1:2]==['extract']:   # python3 tools/ark.py extract USRDIR OUTDIR: unpack every file in the archive
        _,d=load(sys.argv[2]); out=sys.argv[3]
        for f in d['files']:
            if '..' in f['name'].split('/'): continue
            p=os.path.join(out,f['name']); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(read_file(sys.argv[2],d,f))
        print('extracted',len(d['files']),'files to',out); sys.exit()
    enc=open(sys.argv[1],'rb').read(); key,h=decrypt_hdr(enc); d=parse(h)
    print('parts',d['part_count'],'files',len(d['files']),'buckets',len(d['buckets']))
    print('round trip exact:',encrypt_hdr(build(d),key)==enc)
