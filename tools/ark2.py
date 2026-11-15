"""ARK v2 (PS2): single MAIN.ARK with an inline index."""
import struct,os,sys
def entries(path):
    f=open(path,'rb'); h=f.read(4<<20)
    ver,n=struct.unpack_from('<II',h,0); assert ver==2
    E=[struct.unpack_from('<5I',h,8+20*i) for i in range(n)]; p=8+20*n
    sl=struct.unpack_from('<I',h,p)[0]; st=h[p+4:p+4+sl]; q=p+4+sl; cnt=struct.unpack_from('<I',h,q)[0]; O=struct.unpack_from('<%dI'%cnt,h,q+4)
    def s(i):
        if i>=len(O): return ''
        o=O[i]; return st[o:st.index(b'\0',o)].decode('latin-1')
    return [{'offset':e[0],'name':s(e[1]),'dir':s(e[2]),'size':e[3],'inflated':e[4]} for e in E]
def extract(path,out,want=None):
    f=open(path,'rb'); n=0
    for e in entries(path):
        full=os.path.join(e['dir'],e['name']) if e['dir'] else e['name']
        if want and not want(full): continue
        dst=os.path.join(out,full.replace('\\','/')); os.makedirs(os.path.dirname(dst),exist_ok=True)
        f.seek(e['offset']); open(dst,'wb').write(f.read(e['size'])); n+=1
    return n
if __name__=='__main__':
    es=entries(sys.argv[1]); import collections
    print(len(es),'entries'); print(collections.Counter(os.path.splitext(e['name'])[1] for e in es).most_common(15))
    print([os.path.join(e['dir'],e['name']) for e in es if e['name'].endswith('.mid')][:40])
