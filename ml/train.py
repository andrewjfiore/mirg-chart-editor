import sys,os,glob,json,time,random,numpy as np,torch,torch.nn.functional as Fn
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,os.path.join(ROOT,'ml'))
from model import Charter
dev='mps' if torch.backends.mps.is_available() else 'cpu'
files=sorted(glob.glob(os.path.join(ROOT,'ml','data','*.npz'))); names=[os.path.basename(f)[:-4] for f in files]
ps3=[n for n in names if not n.startswith('ps2_')]
TEST=set(ps3[3::8]); VAL=set(ps3[6::8])-TEST; TRAIN=[n for n in names if n not in TEST|VAL]   # PS2 songs only ever train
D={n:dict(np.load(f)) for n,f in zip(names,files)}
for d in D.values(): d['mels']=d['mels'].astype(np.float32); d['mix']=d['mix'].astype(np.float32)
CH=384; PAD=24
def sample(n,k,start):
    d=D[n]; sf_=d['step_frames']; S=len(sf_); s0=start; s1=min(S,s0+CH)
    f0=max(0,int(sf_[s0])-PAD); f1=min(len(d['mix']),int(sf_[s1-1])+PAD+1)
    return d['mels'][k,f0:f1],d['mix'][f0:f1],sf_[s0:s1]-f0,np.arange(s0,s1),d['y'][k,:,s0:s1],int(d['fams'][k])
def bleed(stem,others,a):
    return np.log1p(np.expm1(stem)+a*np.expm1(others))
def batch(B,pool,aug=True):
    items=[]
    for _ in range(B):
        n=random.choice(pool); d=D[n]; k=random.randrange(d['mels'].shape[0]); S=len(d['step_frames'])
        st,mx,sf_,si,y,fam=sample(n,k,random.randrange(0,max(1,S-CH)))
        if aug:
            if random.random()<0.6:
                j=random.choice([q for q in range(d['mels'].shape[0]) if q!=k]); f0=int(d['step_frames'][si[0]])-int(sf_[0])
                st=bleed(st,d['mels'][j,f0:f0+len(st)],random.uniform(0.05,0.35))
            g=random.uniform(-0.6,0.6); st=np.maximum(st+g*0.3,0); mx=np.maximum(mx+random.uniform(-0.3,0.3),0)
        items.append((st,mx,sf_,si,y,fam))
    T=max(len(i[0]) for i in items); S=max(len(i[2]) for i in items)
    st=np.zeros((B,T,64),np.float32); mx=np.zeros((B,T,64),np.float32); sf_=np.zeros((B,S),np.float32); si=np.zeros((B,S),np.int64); y=np.full((B,4,S),-100,np.int64); fam=np.zeros(B,np.int64)
    for b,(a,m,f,i,yy,fa) in enumerate(items):
        st[b,:len(a)]=a; mx[b,:len(m)]=m; sf_[b,:len(f)]=f; si[b,:len(i)]=i; y[b,:,:yy.shape[1]]=yy; fam[b]=fa
    t=lambda a:torch.from_numpy(a).to(dev)
    return t(st),t(mx),t(sf_),t(si),t(y),t(fam)
W=torch.tensor([1.0,2.5,2.5,2.5],device=dev)
def loss_fn(logits,y):
    # logits: B x S x diff x class ; y: B x diff x S  -> both flattened as (S, diff)
    B,S=logits.shape[:2]
    return Fn.cross_entropy(logits.reshape(B*S*4,4),y.permute(0,2,1).reshape(B*S*4),weight=W,ignore_index=-100)
@torch.no_grad()
def predict(model,n,k):
    d=D[n]; S=len(d['step_frames']); out=np.zeros((S,4,4),np.float32); model.eval()
    for s0 in range(0,S,CH-64):
        st,mx,sf_,si,y,fam=sample(n,k,s0); t=lambda a:torch.from_numpy(np.asarray(a))[None].to(dev)
        lo=model(t(st),t(mx),t(sf_),t(si),torch.tensor([fam],device=dev)).softmax(-1)[0].cpu().numpy()
        a=0 if s0==0 else 32; out[s0+a:s0+len(si)]=lo[a:]
    return out
if __name__=='__main__':
    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    model=Charter().to(dev); opt=torch.optim.AdamW(model.parameters(),lr=2e-3,weight_decay=1e-4)
    steps=int(sys.argv[1]) if len(sys.argv)>1 else 3000; sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=2e-3,total_steps=steps)
    print('train',len(TRAIN),'val',sorted(VAL),'test',sorted(TEST),'device',dev,flush=True); best=1e9; t0=time.time()
    for it in range(1,steps+1):
        model.train(); st,mx,sf_,si,y,fam=batch(16,TRAIN); l=loss_fn(model(st,mx,sf_,si,fam),y)
        opt.zero_grad(); l.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); opt.step(); sched.step()
        if it%250==0:
            model.eval(); vl=0
            with torch.no_grad():
                random.seed(123)
                for _ in range(8): st,mx,sf_,si,y,fam=batch(16,sorted(VAL),aug=False); vl+=loss_fn(model(st,mx,sf_,si,fam),y).item()
                random.seed(it)
            vl/=8; print('it %d train %.4f val %.4f  %.0fs'%(it,l.item(),vl,time.time()-t0),flush=True)
            if vl<best: best=vl; torch.save(model.state_dict(),os.path.join(ROOT,'ml','charter.pt'))
    print('best val',best)
