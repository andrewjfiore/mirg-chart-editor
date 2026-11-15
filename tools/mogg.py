"""Unencrypted Harmonix MOGG v10: 20-byte header + seek map + Ogg Vorbis stream."""
import struct,sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
def parse(b):
    ver,ogg_off,mapver,buf,n=struct.unpack_from('<5I',b,0)
    m=[struct.unpack_from('<II',b,20+8*i) for i in range(n)]
    return {'version':ver,'ogg_offset':ogg_off,'map_version':mapver,'buffer':buf,'map':m}
def ogg_pages(o):
    p=0;pages=[]
    while p+27<=len(o):
        assert o[p:p+4]==b'OggS',p
        gran=struct.unpack_from('<q',o,p+6)[0]; nseg=o[p+26]; segs=o[p+27:p+27+nseg]
        size=27+nseg+sum(segs); pages.append((p,gran)); p+=size
    return pages
def build_map(o,step=20000):
    """Seek map: for each target k*step, the last 4 KB-aligned offset X whose sample position
    (end sample of the first packet whose page begins at/after X) is <= target."""
    import vorbis,bisect
    tl,_=vorbis.timeline(o); pb=[r[1] for r in tl]; ends=[r[2] for r in tl]
    nb=(len(o)+4095)//4096; pos=[]
    for blk in range(nb):
        i=bisect.bisect_left(pb,blk*4096)
        pos.append(ends[i] if i<len(tl) else None)
    total=ogg_pages(o)[-1][1]; m=[(0,0)]; k=1
    maxpos=max(x for x in pos if x is not None)
    while k*step<maxpos:
        t=k*step; best=None
        for blk in range(len(pos)):
            if pos[blk] is not None and pos[blk]<=t: best=(blk*4096,pos[blk])
            elif pos[blk] is not None and pos[blk]>t: break
        m.append(best); k+=1
    m.append((0xFFFFFFFF,total))
    return m
def build(ogg,step=20000):
    m=build_map(ogg,step); hdr=struct.pack('<5I',10,20+8*len(m),0x10,step,len(m))+b''.join(struct.pack('<II',a,b) for a,b in m)
    return hdr+ogg
if __name__=='__main__':
    b=open(sys.argv[1],'rb').read(); h=parse(b); o=b[h['ogg_offset']:]
    print({k:v for k,v in h.items() if k!='map'},'entries',len(h['map']),h['map'][:5])
    mine=build_map(o,h['buffer']); print('mine',len(mine),mine[:5]); print('map exact:',mine==h['map'])
    print('rebuild exact:',build(o,h['buffer'])==b)
