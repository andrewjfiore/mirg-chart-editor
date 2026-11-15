"""Demucs 6-stem separation (drums, bass, other, vocals, guitar, piano). Caches stems next to the upload."""
import os,sys,time,numpy as np,soundfile as sf,torch
STEMS=['drums','bass','other','vocals','guitar','piano']
def separate(path,outdir,model_name='htdemucs_6s',progress=None):
    os.makedirs(outdir,exist_ok=True)
    done=[os.path.join(outdir,s+'.wav') for s in STEMS]
    if all(os.path.exists(p) for p in done):
        return {s:p for s,p in zip(STEMS,done)}
    import demucs.api
    dev='cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    sep=demucs.api.Separator(model=model_name,device=dev,progress=False,
        callback=(lambda d: progress and progress(d.get('segment_offset',0)/max(1,d.get('audio_length',1)))) )
    origin,res=sep.separate_audio_file(path)
    out={}
    for s,wav in res.items():
        p=os.path.join(outdir,s+'.wav'); sf.write(p,wav.cpu().numpy().T,sep.samplerate,subtype='FLOAT'); out[s]=p
    return out
if __name__=='__main__':
    t=time.time(); r=separate(sys.argv[1],sys.argv[2]); print({k:os.path.getsize(v) for k,v in r.items()},'%.0fs'%(time.time()-t))
