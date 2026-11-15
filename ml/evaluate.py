"""Score the model vs human charts on held-out songs; calibrate per-difficulty thresholds on validation songs."""
import sys,os,json,numpy as np,torch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,os.path.join(ROOT,'ml'))
import train as T
import weightspace as WS
import decode as DEC, features as F
from model import Charter
DIFF=['Beginner','Intermediate','Advanced','Expert']
def decode(p,th):
    """p: S x 4 x 4 probs -> S x 4 labels."""
    gem=1-p[:,:,0]; lane=p[:,:,1:].argmax(-1)+1; return np.where(gem>=th[None,:],lane,0)
def score(pred,y,tol=0):
    out={}
    for d in range(4):
        P=np.where(pred[:,d]>0)[0]; G=np.where(y[d]>0)[0]
        if tol: hitP=np.array([np.any(np.abs(G-s)<=tol) for s in P]) if len(P) else np.array([]); hitG=np.array([np.any(np.abs(P-s)<=tol) for s in G]) if len(G) else np.array([])
        else: hitP=np.isin(P,G); hitG=np.isin(G,P)
        prec=hitP.mean() if len(P) else 0; rec=hitG.mean() if len(G) else 0
        both=np.intersect1d(P,G); lane=(pred[both,d]==y[d][both]).mean() if len(both) else 0
        out[d]=(prec,rec,2*prec*rec/(prec+rec+1e-9),lane,len(P)/max(1,len(G)))
    return out
def baseline_probs(n,k):
    """Onset strength of the stem at each step + spectral-centroid lane. Same output shape as the model."""
    d=T.D[n]; m=d['mels'][k]; flux=np.concatenate([[0],np.maximum(np.diff(m,axis=0),0).sum(1)]); flux=flux/(flux.max()+1e-6)
    fr=np.clip(np.round(d['step_frames']).astype(int),0,len(m)-1); on=flux[fr]
    cent=(m*np.arange(m.shape[1])).sum(1)/(m.sum(1)+1e-6); c=cent[fr]; q=np.quantile(c,[1/3,2/3]); lane=np.digitize(c,q)
    p=np.zeros((len(fr),4,4),np.float32)
    for dd in range(4): p[:,dd,0]=1-on; p[np.arange(len(fr)),dd,lane+1]=on
    return p
def ws_probs(n,k,th=None):
    d=T.D[n]; return WS.forward(d['mels'][k],d['step_frames'],int(d['fams'][k]),th=th)
def ladder_labels(p,n,k):
    d=T.D[n]; act=DEC.active_steps(d['mels'][k],d['step_frames']); y=np.zeros((len(p),4),np.int8)
    for s_,dd,l in DEC.ladder(p,F.FAMILIES[int(d['fams'][k])],act): y[s_,dd]=l+1
    return y
def report_ladder(name,songs,fn):
    rows=[]; S=[]
    for n in sorted(songs):
        for k in range(T.D[n]['mels'].shape[0]): S.append(score(ladder_labels(fn(n,k),n,k),T.D[n]['y'][k]))
    for d in range(4):
        a=np.array([s[d] for s in S]).mean(0); rows.append((name,'ladder',DIFF[d],*np.round(a,3)))
    return rows
def collect(model,songs,fn):
    R=[]
    for n in sorted(songs):
        for k in range(T.D[n]['mels'].shape[0]): R.append((fn(model,n,k) if model else fn(n,k),T.D[n]['y'][k]))
    return R
def calibrate(R):
    th=np.zeros(4)
    for d in range(4):
        best=(-1,0.5)
        for t in np.linspace(0.05,0.95,37):
            f=np.mean([score(decode(p,np.full(4,t)),y)[d][2] for p,y in R]); best=max(best,(f,t))
        th[d]=best[1]
    return th
def report(name,R,th):
    rows=[]
    for tol in (0,1):
        S=[score(decode(p,th),y,tol) for p,y in R]
        for d in range(4):
            a=np.array([s[d] for s in S]).mean(0); rows.append((name,'exact' if tol==0 else '+-1 step',DIFF[d],*np.round(a,3)))
    return rows
if __name__=='__main__':
    which=sys.argv[1:] or ['trained','weightspace','baseline']; res={}; calib={}
    if os.path.exists(os.path.join(ROOT,'ml','calib.json')): calib=json.load(open(os.path.join(ROOT,'ml','calib.json')))
    rows=[]
    if 'trained' in which:
        model=Charter().to(T.dev); model.load_state_dict(torch.load(os.path.join(ROOT,'ml','charter.pt'),map_location=T.dev))
        th=calibrate(collect(model,T.VAL,T.predict)); calib['trained']=th.tolist(); calib['thresholds']=th.tolist()
        rows+=report('trained',collect(model,T.TEST,T.predict),th)
    if 'weightspace' in which:
        th=calibrate(collect(None,T.VAL,ws_probs)); calib['weightspace']=th.tolist()
        rows+=report('weights',collect(None,T.TEST,lambda n,k:ws_probs(n,k,th)),th)
    if 'ladder' in which:
        thw=np.array(calib.get('weightspace',[0.5]*4)); rows+=report_ladder('weights',T.TEST,lambda n,k:ws_probs(n,k,thw))
        if os.path.exists(os.path.join(ROOT,'ml','charter.pt')) and 'notrained' not in which:
            model=Charter().to(T.dev); model.load_state_dict(torch.load(os.path.join(ROOT,'ml','charter.pt'),map_location=T.dev))
            rows+=report_ladder('trained',T.TEST,lambda n,k:T.predict(model,n,k))
    if 'baseline' in which:
        th=calibrate(collect(None,T.VAL,baseline_probs)); rows+=report('baseline',collect(None,T.TEST,baseline_probs),th)
    json.dump(calib,open(os.path.join(ROOT,'ml','calib.json'),'w'),indent=1)
    print('%-8s %-9s %-13s %6s %6s %6s %6s %7s'%('model','match','difficulty','prec','recall','F1','lane','density'))
    for r in rows: print('%-8s %-9s %-13s %6.3f %6.3f %6.3f %6.3f %7.2f'%r)
    json.dump([list(map(str,r)) for r in rows],open(os.path.join(ROOT,'ml','eval_%s.json'%'_'.join(which)),'w'))
