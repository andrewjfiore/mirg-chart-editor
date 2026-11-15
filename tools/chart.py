"""Chart model: .mid <-> editable JSON (gems per track/difficulty/lane) with lossless round trip."""
import struct,os,sys,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import midps3
DIFF_NAMES=['Beginner','Intermediate','Advanced','Expert']
def lane_of(note):
    if 96<=note<=118 and (note-96)%2==0:
        k=(note-96)//2; return k//3,k%3   # (difficulty, lane)
    return None
def note_of(diff,lane): return 96+6*diff+2*lane
def track_kind(name):
    if 'CATCH' in name: return 'catch'
    if 'FREESTYLE' in name: return 'freestyle'
    if name.startswith('BG_CLICK'): return 'click'
    if name=='WORLD': return 'world'
    return 'other'
def label_of(name):
    m=re.search(r'CATCH:[A-Z]:([^ ]+)',name); return m.group(1) if m else name
def load(mid_path):
    """Returns chart dict. Gems are pulled out of CATCH tracks; every other event is kept raw in 'rest'."""
    tpq,smf=midps3.read_smf(open(mid_path,'rb').read())
    chart={'tpq':tpq,'tracks':[],'tempos':[],'timesig':[],'world':[]}
    for ti,ev in enumerate(smf):
        name=''; rest=[]; gems=[]; open_={}
        for tick,e in ev:
            if e[0]=='meta' and e[1]==3 and not name: name=e[2].decode('latin-1')
        kind=track_kind(name)
        for idx,(tick,e) in enumerate(ev):
            if e[0]=='meta':
                if e[1]==0x51: chart['tempos'].append([tick,int.from_bytes(e[2][:3],'big')])
                if e[1]==0x58: chart['timesig'].append([tick,e[2][0],2**e[2][1]])
                if kind=='world' and e[1]==1: chart['world'].append([tick,e[2].decode('latin-1')])
                rest.append([tick,'meta',e[1],e[2].hex(),idx]); continue
            st,dd=e[1],e[2]; hi=st&0xF0
            if kind=='catch' and hi in(0x80,0x90) and len(dd)==2 and lane_of(dd[0]):
                note,vel=dd
                if hi==0x90 and vel>0:
                    g=[tick,*lane_of(note),0,vel,st&0x0F,None,idx,None]; gems.append(g); open_.setdefault(note,[]).append(g); continue
                q=open_.get(note) or []; g=q.pop(0) if q else None
                if g is not None and g[6] is None:
                    g[3]=tick-g[0]; g[6]=[st,vel]; g[8]=idx; continue
            rest.append([tick,'ch',st,bytes(dd).hex(),idx])
        for g in gems:
            if g[6] is None: g[6]=[0x80|g[5],0x40]
        chart['tracks'].append({'index':ti,'name':name,'kind':kind,'label':label_of(name),
            'gems':[[g[0],g[1],g[2],g[3],g[4]] for g in gems],'gem_meta':[[g[5],g[6][0],g[6][1],g[7],g[8]] for g in gems],'rest':rest,
            'eot':ev[-1][0] if ev else 0})
    return chart
def _vlq(n):
    out=[n&0x7f]; n>>=7
    while n: out.append(0x80|(n&0x7f)); n>>=7
    return bytes(reversed(out))
def save(chart):
    """Chart dict -> SMF bytes (format 1). Gems become note-on/note-off pairs on their lane pitches."""
    trks=[]
    for t in chart['tracks']:
        evs=[]  # (tick, order, seq, bytes)
        BIG=10**9; seq=BIG
        for r in t['rest']:
            tick,kind,a,b=r[:4]; b=bytes.fromhex(b); o=r[4] if len(r)>4 else seq; seq+=1
            if kind=='meta':
                if a==0x2F: continue
                evs.append((tick,o,bytes([0xFF,a])+_vlq(len(b))+b))
            else: evs.append((tick,o,bytes([a])+b))
        meta=t.get('gem_meta') or []
        for i,g in enumerate(t['gems']):
            tick,diff,lane,dur,vel=g[:5]
            ch,offst,offvel,oi,fi=(list(meta[i])+[None,None])[:5] if i<len(meta) and meta[i] else (0,0x80,0x40,None,None)
            n=note_of(diff,lane); dur=dur or 120
            evs.append((tick,oi if oi is not None else seq,bytes([0x90|ch,n,vel]))); seq+=1
            evs.append((tick+dur,fi if fi is not None else seq,bytes([offst,n,offvel]))); seq+=1
        evs.sort(key=lambda e:(e[0],e[1]))
        body=b''; prev=0
        for tick,_,b in evs: body+=_vlq(tick-prev)+b; prev=tick
        eot=max(t.get('eot',0),prev); body+=_vlq(eot-prev)+b'\xff\x2f\x00'
        trks.append(b'MTrk'+struct.pack('>I',len(body))+body)
    return b'MThd'+struct.pack('>IHHH',6,1,len(trks),chart['tpq'])+b''.join(trks)
def compile_chart(chart,tmp_path):
    open(tmp_path,'wb').write(save(chart)); return midps3.compile_mid(tmp_path)
