"""Difficulty ladder decode used for uploads (both models).
Expert takes the most likely steps until it reaches the human gem density for that instrument;
each easier level is picked from the level above (same steps, same lanes), with wider minimum spacing."""
import json,os,numpy as np
ROOT=os.path.dirname(os.path.abspath(__file__))
DENS=json.load(open(os.path.join(ROOT,'density.json')))
SPACING=[5,5,2,1]          # min steps between gems, Beginner..Expert (12 steps per beat)
def _pick(cands,score,n,r):
    chosen=[]; taken=np.zeros(len(score)+2*r+2,bool)
    for s in cands[np.argsort(-score[cands],kind='stable')]:
        if len(chosen)>=n: break
        if taken[s:s+2*r+1].any(): continue
        chosen.append(s); taken[s+r]=True
    return np.sort(np.array(chosen,int))
def ladder(probs,family,active):
    """probs: S x 4 x 4; family: name; active: bool S (instrument audible). Returns list of (step, diff, lane)."""
    S=len(probs); dens=DENS.get(family,DENS['_all']); beats=active.sum()/12.0; scale=DENS.get('_scale',[1,1,1,1])
    gem=1-probs[:,:,0]; out=[]; prev=None; lanes=probs[:,3,1:].argmax(-1)
    for d in (3,2,1,0):
        n=int(round(dens[d]*scale[d]*beats))
        cands=np.where(active&(gem[:,d]>=0.02))[0] if prev is None else prev
        sel=_pick(cands,gem[:,d],n,SPACING[d])
        if prev is None: lane_d=lanes
        out+=[(int(s),d,int(lanes[s])) for s in sel]; prev=sel
    return out
def active_steps(stem_mel,step_frames):
    e=stem_mel.astype(np.float32).sum(1); fr=np.clip(np.round(step_frames).astype(int),0,len(e)-1)
    ref=np.percentile(e,95); return e[fr]>0.08*ref
