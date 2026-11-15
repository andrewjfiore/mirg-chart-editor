"""Fun layers for the weight-space charter. All numbers hand-written; targets come from measured human-chart habits
(training songs): bars repeat 88-96%, lane moves same/step/jump = 27/49/24%, no same-lane bursts, every active bar
keeps a gem on every difficulty, density follows loudness (r about 0.4)."""
import numpy as np,json,os
ROOT=os.path.dirname(os.path.abspath(__file__)); BAR=48
DENS=json.load(open(os.path.join(ROOT,'density.json')))
FUN={
 'lane_logp': np.log(np.array([0.27,0.49,0.24])),   # transition weights: same lane, one lane over, left<->right jump
 'emit_gain': 1.2,                                   # how strongly the pitch contour pulls the lane
 'jack_steps': 3,                                    # same lane within 3 steps (a 16th) is a burst
 'jack_logp': -6.0,
 'energy_gamma': 0.25,                               # gem scores tilted by bar loudness^gamma
 'keep_lane': 1.0,                                   # log-odds bonus for the lane the onset/pitch rule chose
 'jump_bonus': 1.5,                                  # extra log weight for left<->right jumps on a strong onset
 'motif_tau': 0.93,                                  # bars whose audio fingerprints match above this get the same pattern
 'motif_bands': 16, 'motif_pos': 12,
 'spacing': [5,5,2,1],
}
def bar_energy(stem_mel,fr,S):
    e=np.expm1(stem_mel.astype(np.float32)).sum(1)[fr]; nb=(S+BAR-1)//BAR
    return np.array([e[b*BAR:(b+1)*BAR].mean() if b*BAR<S else 0 for b in range(nb)])
def fingerprints(stem_mel,fr,S):
    m=stem_mel.astype(np.float32); nb=S//BAR; F=[]
    band=np.array_split(np.arange(m.shape[1]),FUN['motif_bands'])
    for b in range(nb):
        rows=m[fr[b*BAR:(b+1)*BAR]]; pos=np.array_split(rows,FUN['motif_pos'])
        v=np.array([[p[:,bi].mean() for bi in band] for p in pos]).ravel(); v=v-v.mean(); F.append(v/(np.linalg.norm(v)+1e-6))
    return np.array(F)
def _pick_bar(cands,score,n,r):
    chosen=[]
    for s in cands[np.argsort(-score[cands],kind='stable')]:
        if len(chosen)>=n: break
        if any(abs(s-c)<=r for c in chosen): continue
        chosen.append(s)
    return sorted(chosen)
def place(gem,active,family,e_bar,S,scale=(1,1,1,1)):
    """Per-bar gem budgets that follow loudness; every active bar keeps >=1 gem on every difficulty; easier levels nest."""
    dens=DENS.get(family,DENS['_all']); nb=(S+BAR-1)//BAR; act_bar=np.array([active[b*BAR:(b+1)*BAR].any() for b in range(nb)])
    w=np.where(act_bar,np.maximum(e_bar,1e-9)**FUN['energy_gamma'],0); w=w/(w.sum()+1e-12)
    sel={}; prev=None
    for d in (3,2,1,0):
        total=dens[d]*scale[d]*active.sum()/12.0; quota=np.where(act_bar,np.maximum(1,np.round(w*total)),0).astype(int)
        steps=[]
        for b in range(nb):
            if not quota[b]: continue
            lo,hi=b*BAR,min(S,(b+1)*BAR)
            c=np.arange(lo,hi)[active[lo:hi]] if prev is None else np.array([s for s in prev if lo<=s<hi],int)
            if not len(c): continue
            steps+=_pick_bar(c,gem[:,d],int(quota[b]),FUN['spacing'][d])
        sel[d]=np.array(sorted(steps),int); prev=sel[d]
    return sel
def lanes_viterbi(steps,z):
    """Lane grammar: emission from pitch contour z (higher pitch -> right), transitions from human habits, no bursts."""
    n=len(steps)
    if n==0: return np.zeros(0,int)
    em=np.stack([-FUN['emit_gain']*np.maximum(z[steps],0)*1.0+FUN['emit_gain']*np.minimum(z[steps],0)*0,
                 -FUN['emit_gain']*np.abs(z[steps])*0.5,
                 FUN['emit_gain']*np.maximum(z[steps],0)-FUN['emit_gain']*np.maximum(-z[steps],0)],1)
    em[:,0]=FUN['emit_gain']*np.maximum(-z[steps],0)-FUN['emit_gain']*np.maximum(z[steps],0)
    D=np.full((n,3),-1e9); B=np.zeros((n,3),int); D[0]=em[0]
    for i in range(1,n):
        gap=steps[i]-steps[i-1]
        for l in range(3):
            tr=np.array([FUN['lane_logp'][abs(l-p)] for p in range(3)])
            if gap<=FUN['jack_steps']: tr[l]+=FUN['jack_logp']
            v=D[i-1]+tr; B[i,l]=int(v.argmax()); D[i,l]=v.max()+em[i,l]
    path=np.zeros(n,int); path[-1]=int(D[-1].argmax())
    for i in range(n-1,0,-1): path[i-1]=B[i,path[i]]
    return path
def motif_copy(y,fp):
    """Bars whose audio matches get one shared pattern on every difficulty: the group's typical bar (median gem count),
    so neither a quiet first occurrence (an intro) nor one busy outlier sets the density for the rest of the song."""
    nb=len(fp)
    if nb<2: return y
    sim=fp@fp.T; parent=list(range(nb))
    def find(i):
        while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for i in range(nb):
        for j in np.where(sim[i,:i]>=FUN['motif_tau'])[0]: parent[find(i)]=find(int(j))
    groups={}
    for i in range(nb): groups.setdefault(find(i),[]).append(i)
    count=lambda i: int((y[i*BAR:(i+1)*BAR,3]>0).sum())
    for g in groups.values():
        if len(g)<2: continue
        cs=sorted(count(i) for i in g); med=cs[len(cs)//2]
        t=min(g,key=lambda i:(abs(count(i)-med),i)); pat=y[t*BAR:(t+1)*BAR].copy()
        for i in g: y[i*BAR:(i+1)*BAR]=pat
    return y
def place_tilt(probs,active,family,e_bar,S,scale):
    """Ladder pick on loudness-tilted scores, then make sure every active bar keeps >=1 gem on each difficulty."""
    import decode as DEC
    nb=(S+BAR-1)//BAR; eb=np.repeat(e_bar/(np.median(e_bar[e_bar>0])+1e-9) if (e_bar>0).any() else np.ones(nb),BAR)[:S]
    p=probs.copy(); g=(1-p[:,:,0])*np.clip(eb,1e-3,None)[:,None]**FUN['energy_gamma']; g=np.clip(g,0,1); p[:,:,0]=1-g
    L=DEC.ladder(p,family,active); sel={d:set(s_ for s_,dd,_ in L if dd==d) for d in range(4)}
    for b in range(nb):
        lo,hi=b*BAR,min(S,(b+1)*BAR)
        if not active[lo:hi].any(): continue
        for d in (3,2,1,0):
            if any(lo<=x<hi for x in sel[d]): continue
            pool=[x for x in (sel[d+1] if d<3 else range(lo,hi)) if lo<=x<hi and active[x]]
            if pool: best=max(pool,key=lambda x:g[x,d]); [sel[q].add(best) for q in range(d,4)]
    return {d:np.array(sorted(sel[d]),int) for d in range(4)}
def lanes_grammar(steps,base,strength):
    """Viterbi over lanes: emission keeps the base lane choice, transitions follow human habits, bursts are blocked."""
    n=len(steps)
    if n==0: return np.zeros(0,int)
    em=np.full((n,3),0.0); em[np.arange(n),base]=FUN['keep_lane']
    D=np.zeros((n,3)); B=np.zeros((n,3),int); D[0]=em[0]
    for i in range(1,n):
        gap=steps[i]-steps[i-1]
        for l in range(3):
            tr=np.array([FUN['lane_logp'][abs(l-q)]+(FUN['jump_bonus']*strength[i] if abs(l-q)==2 else 0) for q in range(3)])
            if gap<=FUN['jack_steps']: tr[l]+=FUN['jack_logp']
            v=D[i-1]+tr; B[i,l]=int(v.argmax()); D[i,l]=v.max()+em[i,l]
    path=np.zeros(n,int); path[-1]=int(D[-1].argmax())
    for i in range(n-1,0,-1): path[i-1]=B[i,path[i]]
    return path
def chart(probs,stem_mel,step_frames,family,active,scale=(1,1,1,1),motif=True,viterbi=True,quota=True):
    """probs: S x 4 x 4 from weightspace.forward. Returns y: S x 4 labels (0 none, 1-3 lane)."""
    S=len(probs); fr=np.clip(np.round(step_frames).astype(int),0,len(stem_mel)-1)
    m=stem_mel.astype(np.float32); cen=(m*np.arange(m.shape[1])).sum(1)/(m.sum(1)+1e-6); c=cen[fr]
    def mov(x,n):
        k=np.ones(n)/n; return np.convolve(x,k,'same')
    con=c-mov(c,24); z=con/(np.sqrt(mov(con**2,96))+1e-6)
    gem=1-probs[:,:,0]
    if quota: sel=place_tilt(probs,active,family,bar_energy(stem_mel,fr,S),S,scale)
    else:
        import decode as DEC; L=DEC.ladder(probs,family,active); sel={d:np.array(sorted(s_ for s_,dd,_ in L if dd==d),int) for d in range(4)}
    y=np.zeros((S,4),np.int8)
    base=np.array([int(probs[s_,3,1:].argmax()) for s_ in sel[3]],int)
    if viterbi:
        on=gem[sel[3],3] if len(sel[3]) else np.zeros(0); st=(on-on.mean())/(on.std()+1e-6) if len(on) else on
        lane_e=dict(zip(sel[3],lanes_grammar(sel[3],base,np.clip(st,0,2))))
    else: lane_e=dict(zip(sel[3],base))
    for d in (3,2,1,0):
        for s in sel[d]: y[s,d]=lane_e.get(s,1)+1
    if motif: y=motif_copy(y,fingerprints(stem_mel,fr,S))
    return y
