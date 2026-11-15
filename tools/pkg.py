import sys,struct,os
from Crypto.Cipher import AES
from Crypto.Util import Counter
# The PS3 package key is not kept in the repo: set PKG_KEY (32 hex digits) or put it in work/pkg_key.txt.
_kf=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'work','pkg_key.txt')
_kh=os.environ.get('PKG_KEY') or (open(_kf).read().strip() if os.path.exists(_kf) else '')
if len(_kh)!=32: sys.exit('pkg.py needs the PS3 package key: set PKG_KEY or write it to '+_kf)
KEY=bytes.fromhex(_kh)
p,out=sys.argv[1],sys.argv[2]
f=open(p,'rb'); h=f.read(0x100)
cnt=struct.unpack('>I',h[0x14:0x18])[0]
doff,dsz=struct.unpack('>QQ',h[0x20:0x30]); riv=int.from_bytes(h[0x70:0x80],'big')
def dec(off,size):
    blk=off//16; skip=off%16
    f.seek(doff+blk*16); d=f.read(size+skip)
    c=AES.new(KEY,AES.MODE_CTR,counter=Counter.new(128,initial_value=(riv+blk)%(1<<128)))
    return c.decrypt(d)[skip:skip+size]
tab=dec(0,cnt*32)
for i in range(cnt):
    no,ns,o,s,fl,_=struct.unpack('>IIQQII',tab[i*32:i*32+32])
    name=dec(no,ns).decode('utf-8','replace'); t=fl&0xff
    print(f'{t:02x} {s:>12} {name}')
    path=os.path.join(out,name.lstrip('/'))
    if t in (4,0x12): os.makedirs(path,exist_ok=True); continue
    if '--list' in sys.argv: continue
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,'wb') as w:
        pos=0
        while pos<s:
            n=min(64<<20,s-pos); w.write(dec(o+pos,n)); pos+=n
