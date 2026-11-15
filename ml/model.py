import torch,torch.nn as nn,torch.nn.functional as Fn
class Charter(nn.Module):
    """Audio (stem + mix log-mel) -> per grid step, per difficulty: none/L/M/R."""
    def __init__(s,nmels=64,h=160,nfam=7,steps_per_beat=12):
        super().__init__()
        s.inp=nn.Conv1d(2*nmels,h,5,padding=2)
        s.blocks=nn.ModuleList([nn.Conv1d(h,h,3,padding=d,dilation=d) for d in (1,2,4,8,1)])
        s.norms=nn.ModuleList([nn.GroupNorm(8,h) for _ in s.blocks])
        s.beat=nn.Embedding(steps_per_beat,24); s.bar=nn.Embedding(4,8); s.fam=nn.Embedding(nfam,16)
        s.gru=nn.GRU(h*3+24+8+16,h,num_layers=2,batch_first=True,bidirectional=True,dropout=0.2)
        s.head=nn.Linear(2*h,16); s.spb=steps_per_beat
    def forward(s,stem,mix,step_frames,step_idx,fam):
        # stem,mix: B x T x M ; step_frames: B x S (float frame idx, local to the chunk); step_idx: B x S absolute step; fam: B
        x=torch.cat([stem,mix],-1).transpose(1,2)
        x=Fn.gelu(s.inp(x))
        for c,n in zip(s.blocks,s.norms): x=x+Fn.gelu(n(c(x)))
        T=x.shape[-1]; fr=step_frames.round().long()
        def g(off): 
            i=(fr+off).clamp(0,T-1); return torch.gather(x,2,i.unsqueeze(1).expand(-1,x.shape[1],-1))
        z=torch.cat([g(-1),g(0),g(1)],1).transpose(1,2)          # B x S x 3h
        b=s.beat(step_idx%s.spb); br=s.bar((step_idx//s.spb)%4); f=s.fam(fam)[:,None,:].expand(-1,z.shape[1],-1)
        o,_=s.gru(torch.cat([z,b,br,f],-1))
        return s.head(o).view(o.shape[0],o.shape[1],4,4)        # B x S x diff x class
