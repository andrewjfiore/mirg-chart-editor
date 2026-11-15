"""Harmonix Forge MidiFileResource (.mid_ps3) reader/writer. Big-endian (PS3)."""
import struct,sys
class R:
    def __init__(s,b): s.b=b; s.p=0
    def u8(s): v=s.b[s.p]; s.p+=1; return v
    def u16(s): v=struct.unpack_from('>H',s.b,s.p)[0]; s.p+=2; return v
    def u32(s): v=struct.unpack_from('>I',s.b,s.p)[0]; s.p+=4; return v
    def i32(s): v=struct.unpack_from('>i',s.b,s.p)[0]; s.p+=4; return v
    def f32(s): v=struct.unpack_from('>f',s.b,s.p)[0]; s.p+=4; return v
    def raw(s,n): v=s.b[s.p:s.p+n]; s.p+=n; return v
    def str_(s): n=s.u32(); return s.raw(n).decode('latin-1')
def read(b):
    r=R(b); d={}
    d['magic']=r.u32(); d['last_track_final_tick']=r.u32()
    d['tracks']=[]
    for _ in range(r.u32()):
        t={'unk':r.u8(),'unk2':r.i32(),'msgs':[]}
        for _ in range(r.u32()):
            tick=r.u32(); kind=r.u8(); data=r.raw(3)
            t['msgs'].append((tick,kind,data))
        t['strings']=[r.str_() for _ in range(r.u32())]
        d['tracks'].append(t)
    d['tail_offset']=r.p
    d['tail']=b[r.p:]
    return d
if __name__=='__main__':
    d=read(open(sys.argv[1],'rb').read())
    print('magic',d['magic'],'lastTFT',d['last_track_final_tick'],'tracks',len(d['tracks']))
    for t in d['tracks']:
        kinds={}
        for m in t['msgs']: kinds[m[1]]=kinds.get(m[1],0)+1
        print(' unk',t['unk'],t['unk2'],'msgs',len(t['msgs']),'kinds',kinds,'strings',len(t['strings']),t['strings'][:2])
    print('tail',len(d['tail']),d['tail'][:96].hex())

# ---------- writer / compiler ----------
def _w32(v): return struct.pack('>I',v&0xffffffff)
def _ws(s): b=s.encode('latin-1'); return _w32(len(b))+b
def write(d):
    out=[_w32(d['magic']),_w32(d['last_track_final_tick']),_w32(len(d['tracks']))]
    for t in d['tracks']:
        out.append(bytes([t['unk']])+struct.pack('>i',t['unk2'])+_w32(len(t['msgs'])))
        out.append(b''.join(_w32(tk)+bytes([k])+bytes(dt) for tk,k,dt in t['msgs']))
        out.append(_w32(len(t['strings']))+b''.join(_ws(s) for s in t['strings']))
    return b''.join(out)+d['tail']

META_TYPES={1:1,2:2,3:3,4:4,5:5,6:6,7:7}
def read_smf(b):
    """Minimal raw SMF reader: keeps out-of-range data bytes exactly. Returns (tpq, [[(tick,event)]])."""
    assert b[:4]==b'MThd'; hl=struct.unpack_from('>I',b,4)[0]
    fmt,ntr,tpq=struct.unpack_from('>HHH',b,8); p=8+hl; tracks=[]
    while p<len(b) and len(tracks)<ntr:
        tag=b[p:p+4]; ln=struct.unpack_from('>I',b,p+4)[0]; q=p+8; end=q+ln; p=end
        if tag!=b'MTrk': continue
        tick=0; run=None; ev=[]
        while q<end:
            dt=0
            while True:
                c=b[q]; q+=1; dt=(dt<<7)|(c&0x7f)
                if c<0x80: break
            tick+=dt; st=b[q]
            if st==0xFF:
                typ=b[q+1]; q+=2; n=0
                while True:
                    c=b[q]; q+=1; n=(n<<7)|(c&0x7f)
                    if c<0x80: break
                ev.append((tick,('meta',typ,b[q:q+n]))); q+=n
            elif st in(0xF0,0xF7):
                q+=1; n=0
                while True:
                    c=b[q]; q+=1; n=(n<<7)|(c&0x7f)
                    if c<0x80: break
                q+=n
            else:
                if st&0x80: run=st; q+=1
                hi=run&0xF0; nd=1 if hi in(0xC0,0xD0) else 2
                ev.append((tick,('ch',run,tuple(b[q:q+nd])))); q+=nd
        tracks.append(ev)
    return tpq,tracks
def ORDER(m):
    """Same-tick order used by the Harmonix compiler: meta, note-off, controller, note-on."""
    hi=m[2][0]&0xF0
    return 0 if m[1]!=1 else (1 if hi==0x80 else (3 if hi==0x90 else 2))
def compile_mid(path):
    """Standard MIDI (.mid) -> .mid_ps3 bytes."""
    tpq,smf=read_smf(open(path,'rb').read())
    if tpq!=480: smf=[[(t*480//tpq,e) for t,e in ev] for ev in smf]; tpq=480
    tracks=[];eots=[];tempos=[];sigs=[];names=[]
    for ti,ev in enumerate(smf):
        msgs=[]; strs=[]; tick=0; named=False
        for tick,e in ev:
            if e[0]=='ch':
                st,dd=e[1],e[2]; d1=dd[0]; d2=dd[1] if len(dd)>1 else 0
                if st&0xF0==0x90 and d2==0: st=0x80|(st&0x0F)
                msgs.append((tick,1,(st,d1,d2)))
            else:
                typ,data=e[1],e[2]
                if typ==0x2F: continue
                if typ==0x51:
                    msgs.append((tick,2,tuple(data[:3]))); tempos.append((tick,int.from_bytes(data[:3],'big')))
                elif typ==0x58:
                    num,den=data[0],2**data[1]; msgs.append((tick,4,(num,den,0))); sigs.append((tick,num,den))
                elif typ in META_TYPES:
                    txt=data.decode('latin-1')
                    msgs.append((tick,8,(typ,len(strs)>>8,len(strs)&0xff))); strs.append(txt)
                    if typ==3 and not named: names.append(txt); named=True
        if not named: names.append('')
        eots.append(ev[-1][0] if ev else 0)
        msgs.sort(key=lambda m:(m[0],ORDER(m)))
        chans=[m[2][0]&0x0F for m in msgs if m[1]==1]
        tracks.append({'unk':1,'unk2':chans[0] if chans else -1,'msgs':msgs,'strings':strs})
    ft=max(eots)+1
    tmap=[];ms=0.0;pt=0;ptempo=500000
    for tk,tp in (sorted(tempos) or [(0,500000)]):
        ms+=(tk-pt)*ptempo/tpq/1000.0; tmap.append((ms,tk,tp)); pt,ptempo=tk,tp
    sigs=sorted(sigs) or [(0,4,4)]; smap=[];meas=0;pt=0;pnum,pden=sigs[0][1],sigs[0][2]
    for tk,num,den in sigs:
        if tk>pt: meas+=(tk-pt)//(tpq*4*pnum//pden)
        smap.append((meas,tk,num,den)); pt,pnum,pden=tk,num,den
    blen=tpq*4*pnum//pden; measures=meas+-(-(ft-1-pt)//blen)
    tail=_w32(ft)+_w32(measures)+b'\0'*24+_w32(ft-1)+struct.pack('>ff',-1.0,-1.0)+bytes.fromhex('abcdabcdabcdabcd')
    tail+=_w32(len(tmap))+b''.join(struct.pack('>fIi',a,b,c) for a,b,c in tmap)
    tail+=_w32(len(smap))+b''.join(struct.pack('>iIHH',a,b,c,e) for a,b,c,e in smap)
    tail+=_w32(0)+_w32(0)+_w32(len(names))+b''.join(_ws(n) for n in names)
    return write({'magic':2,'last_track_final_tick':eots[-1],'tracks':tracks,'tail':tail})
