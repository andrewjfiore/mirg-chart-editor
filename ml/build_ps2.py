"""PS2 songs -> ml/data/ps2_<song>.npz. Demucs stems from the stereo mix; per-song audio offset from sync check."""
import sys,os,re,json,numpy as np,soundfile as sf
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0]=[os.path.join(ROOT,'tools'),os.path.join(ROOT,'ml'),ROOT]
import chart,features as F,separate
ST=os.path.join(ROOT,'work','ps2','stems'); ARKS=os.path.join(ROOT,'work','ps2','ark','songs'); OUT=os.path.join(ROOT,'ml','data')
STEM_OF={'drums':'drums','bass':'bass','guitar':'guitar','vox':'vocals','keys':'piano','synth':'other','other':'other'}
def synced():
    out={}
    for line in open(os.path.join(ST,'verify.txt')):
        m=re.match(r'(\w+)\s+2\s+48000\s+\|(.*)',line)
        if not m: continue
        lags=[int(x) for x in re.findall(r'T\d\s+([+-]\d+)',m.group(2))]; rat=[float(x) for x in re.findall(r'T\d\s+[+-]\d+\s+([\d.]+)',m.group(2))]
        if lags and np.median(rat)>=1.2: out[m.group(1)]=int(np.median(lags))
    return out
def build(song,lag):
    mixp=os.path.join(ST,song,'mix.wav'); stems=separate.separate(mixp,os.path.join(ST,song,'demucs'))
    c=chart.load(os.path.join(ARKS,song,song+'_g.mid')); tpq=c['tpq']; catch=[t for t in c['tracks'] if t['kind']=='catch'][:6]
    if not catch: return 'skipped: no CATCH tracks'
    mix,sr=sf.read(mixp,dtype='float32'); mixmel=F.logmel(mix.mean(1),sr)
    cache={}; mels=[]; fams=[]
    for t in catch:
        fam=F.family(t['label']); key=STEM_OF[F.FAMILIES[fam]]
        if key not in cache: a,s2=sf.read(stems[key],dtype='float32'); cache[key]=F.logmel(a.mean(1),s2)
        mels.append(cache[key]); fams.append(fam)
    n_frames=min(len(m) for m in mels+[mixmel]); mels=np.stack([m[:n_frames] for m in mels]); mixmel=mixmel[:n_frames]
    end_tick=max(tt['eot'] for tt in c['tracks']); n_steps=int(end_tick*480/tpq)//F.STEP_TICKS+1
    sfr=F.step_frames(n_steps,c['tempos'],tpq)+lag*256/48000*F.SR/F.HOP     # audio runs `lag` frames (256 @ 48 kHz) behind the chart
    n_steps=int((sfr<n_frames-1).sum()); sfr=sfr[:n_steps]
    y=np.zeros((len(catch),4,n_steps),np.int8)
    for k,t in enumerate(catch):
        for g in t['gems']:
            s=int(round(g[0]*480/tpq/F.STEP_TICKS))
            if s<n_steps: y[k,g[1],s]=g[2]+1
    np.savez_compressed(os.path.join(OUT,'ps2_'+song+'.npz'),mels=mels,mix=mixmel,step_frames=sfr.astype(np.float32),y=y,fams=np.array(fams),labels=np.array([t['label'] for t in catch]))
    return n_steps,int((y>0).sum())
if __name__=='__main__':
    S=synced(); print('synced songs',len(S),S,flush=True)
    for song,lag in sorted(S.items()):
        if os.path.exists(os.path.join(OUT,'ps2_'+song+'.npz')): continue
        print(song,'lag',lag,'steps/gems',build(song,lag),flush=True)
