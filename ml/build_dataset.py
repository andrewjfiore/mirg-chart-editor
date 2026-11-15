"""PS3 songs -> ml/data/<song>.npz : mel per catch track + mix, step frame map, labels [track, diff, step] in {0 none,1 L,2 M,3 R}."""
import sys,os,io,glob,json,numpy as np,soundfile as sf
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0]=[os.path.join(ROOT,'tools'),os.path.join(ROOT,'ml'),ROOT]
import chart,mogg,features as F,server
SONGS=os.path.join(ROOT,'work','ark','ps3','songs'); OUT=os.path.join(ROOT,'ml','data'); os.makedirs(OUT,exist_ok=True)
SKIP={'tut0','tut1','tutc','credits'}
def build(sid):
    c=chart.load(os.path.join(SONGS,sid,sid+'.mid')); tpq=c['tpq']
    info=server.audio_info(sid); playable=[t for t in info['tracks'] if not t['name'].lower().startswith(('freestyle','bg_click'))]
    catch=[t for t in c['tracks'] if t['kind']=='catch']
    b=open(os.path.join(SONGS,sid,sid+'.mogg'),'rb').read(); x,sr=sf.read(io.BytesIO(b[mogg.parse(b)['ogg_offset']:]),dtype='float32')
    mels=[]; fams=[]
    for k,t in enumerate(catch):
        ch=playable[k]['channels'] if k<len(playable) else []
        mono=x[:,ch].mean(1) if ch else np.zeros(len(x),np.float32)
        mels.append(F.logmel(mono,sr)); fams.append(F.family(t['label']))
    mix=F.logmel(x.mean(1),sr)
    n_frames=min(len(m) for m in mels+[mix]); mels=np.stack([m[:n_frames] for m in mels]); mix=mix[:n_frames]
    end_tick=max(tt['eot'] for tt in c['tracks']); n_steps=int(end_tick*480/tpq)//F.STEP_TICKS+1
    sf_=F.step_frames(n_steps,c['tempos'],tpq); keep=sf_<n_frames-1; n_steps=int(keep.sum()); sf_=sf_[:n_steps]
    y=np.zeros((len(catch),4,n_steps),np.int8); off=0
    for k,t in enumerate(catch):
        for g in t['gems']:
            s=int(round(g[0]*480/tpq/F.STEP_TICKS))
            if s<n_steps: y[k,g[1],s]=g[2]+1
            else: off+=1
    np.savez_compressed(os.path.join(OUT,sid+'.npz'),mels=mels,mix=mix,step_frames=sf_.astype(np.float32),y=y,fams=np.array(fams),
        labels=np.array([t['label'] for t in catch]))
    return n_steps,len(catch),off
if __name__=='__main__':
    ids=sorted(d for d in os.listdir(SONGS) if d not in SKIP and os.path.exists(os.path.join(SONGS,d,d+'.mogg')))
    for sid in ids:
        n,k,off=build(sid); print(sid,'steps',n,'tracks',k,'gems past audio end',off,flush=True)
