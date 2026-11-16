"""Tempo map + downbeat from a mix using Beat This! (CPJKU), then a least-squares constant-tempo fit.
Falls back to a per-beat tempo map when the song's tempo drifts."""
import numpy as np,torch
_A=None
# Beat This! weights (MIT). The authors' server rate-limits downloads, so hash-pinned Hugging Face copies go first.
_SHA='8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331'
_URLS=['https://huggingface.co/Audante/beat-this-final0/resolve/main/beat_this-final0.ckpt',
       'https://huggingface.co/teamup-tech/Beat-This-weights/resolve/main/final0.ckpt',
       'https://huggingface.co/oulianov/beat_this/resolve/main/final0.ckpt',
       'https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt']
def _checkpoint():
    import os
    dst=os.path.join(torch.hub.get_dir(),'checkpoints','beat_this-final0.ckpt')   # same file name Beat This caches under
    if os.path.exists(dst): return dst
    os.makedirs(os.path.dirname(dst),exist_ok=True); errs=[]
    for u in _URLS:
        try: torch.hub.download_url_to_file(u,dst,hash_prefix=_SHA); return dst   # temp file, sha256 check, then rename
        except Exception as e: errs.append(f'{u}: {e}')
    raise RuntimeError(f'Could not download the beat model. Download it from {_URLS[0]} and save it as {dst}\n'+'\n'.join(errs))
def _model():
    global _A
    if _A is None:
        from beat_this.inference import Audio2Beats
        _A=Audio2Beats(checkpoint_path=_checkpoint(),device='cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu',dbn=False)
    return _A
def track(mix,sr,beats_per_bar=4,min_lead_beats=8):
    y=mix.mean(1) if mix.ndim==2 else mix
    bt,db=_model()(y,sr); bt=np.asarray(bt,float); db=np.asarray(db,float)
    # inlier search: period and phase that put the most detected beats within 20 ms of the grid
    ibi=np.diff(bt); hist,edges=np.histogram(ibi,bins=np.arange(0.2,1.5,0.01)); per0=float(edges[hist.argmax()]+0.005)
    best=(-1,per0,0.0)
    for per in per0*np.linspace(0.96,1.04,4001):
        r=np.mod(bt,per); h=np.histogram(r,bins=80,range=(0,per))[0]; w=max(1,int(round(0.02/per*80)))
        hh=np.concatenate([h,h[:2*w]]); cs=np.convolve(hh,np.ones(2*w+1),'valid')[:80]; i=int(cs.argmax())
        if cs[i]>best[0]: best=(cs[i],per,(i+0.5)*per/80)
    _,per,ph=best
    k=np.round((bt-ph)/per); resid=bt-(ph+per*k); inl=np.abs(resid)<0.03
    A=np.stack([k[inl],np.ones(inl.sum())],1); per,ph=np.linalg.lstsq(A,bt[inl],rcond=None)[0]
    k=np.round((bt-ph)/per); resid=bt-(ph+per*k); inl=np.abs(resid)<0.03
    rms=float(np.sqrt(np.mean(resid[inl]**2))); per=float(per); ph=float(ph%per)
    if 60/per<95: per/=2   # half-time lock: the supported songs run 100-200 BPM
    # polish: onset strength summed on the grid, period within +-0.3%, phase within +-20 ms
    import librosa
    y22=librosa.resample(y,orig_sr=sr,target_sr=22050); oenv=librosa.onset.onset_strength(y=y22,sr=22050,hop_length=256)
    te=np.arange(len(oenv))/(22050/256)-0.034; dur=te[-1]
    def sc(pp,phh): return np.interp(np.arange(phh,dur,pp),te,oenv).sum()/max(1,int(dur/pp))
    best=(sc(per,ph),per,ph)
    for pp in per*np.linspace(0.997,1.003,241):
        for phh in ph+np.linspace(-0.02,0.02,21):
            v=sc(pp,phh)
            if v>best[0]: best=(v,pp,phh)
    _,per,ph=best; ph=ph%per
    # downbeat phase: beat index mod 4 that most detected downbeats fall on
    if len(db):
        idx=np.round((db-ph)/per).astype(int); bp=int(np.bincount(idx%beats_per_bar,minlength=beats_per_bar).argmax())
    else: bp=0
    first_down=ph+bp*per
    while first_down-per*beats_per_bar>=-1e-9: first_down-=per*beats_per_bar
    bars=int(np.ceil((min_lead_beats*per-first_down)/(per*beats_per_bar))); lead=bars*beats_per_bar*per-first_down
    out={'lead_sec':float(lead),'bpm':float(60/per),'period':float(per),'first_downbeat_sec':float(first_down),'fit_rms_ms':rms*1000,'n_beats':len(bt)}
    if rms<0.015:
        out['tempos']=[[0,int(round(per*1e6))]]
    else:   # drifting tempo: one tempo per detected beat, aligned so tick 0 = start of the padded audio
        t=np.concatenate([[first_down+lead-lead],bt[bt>first_down]])+lead  # beat times after padding
        grid=np.concatenate([[0.0],t]); tempos=[]
        start=first_down+lead
        b=np.concatenate([np.arange(0,start-1e-9,per) if False else [],[start],bt[bt>first_down+1e-3]+lead])
        tempos=[[0,int(round(start/((start/per) if start>0 else 1)*1e6))]]
        ticks=int(round(start/per))*480; tempos=[[0,int(round(per*1e6))]]
        for i in range(len(b)-1):
            tempos.append([ticks+i*480,int(round((b[i+1]-b[i])*1e6))])
        out['tempos']=tempos
    return out
if __name__=='__main__': print(_checkpoint())   # fetch the beat model ahead of time
