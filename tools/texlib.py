import numpy as np
def c565(c):
    r=(c>>11&31)*255//31; g=(c>>5&63)*255//63; b=(c&31)*255//31
    return np.stack([r,g,b],-1)
def dxt_color(blocks):  # blocks: (N,8) uint8
    c0=blocks[:,0].astype(np.uint32)|blocks[:,1].astype(np.uint32)<<8
    c1=blocks[:,2].astype(np.uint32)|blocks[:,3].astype(np.uint32)<<8
    bits=blocks[:,4:8].copy().view('<u4')[:,0]
    a=c565(c0).astype(np.int32); b=c565(c1).astype(np.int32)
    gt=(c0>c1)[:,None]
    c2=np.where(gt,(2*a+b)//3,(a+b)//2); c3=np.where(gt,(a+2*b)//3,0)
    pal=np.stack([a,b,c2,c3],1)  # N,4,3
    idx=(bits[:,None]>>(2*np.arange(16)))&3
    return np.take_along_axis(pal,idx[:,:,None].repeat(3,2),1)  # N,16,3
def tile(px,w,h):
    bw,bh=max(1,w//4),max(1,h//4)
    return px.reshape(bh,bw,4,4,3).transpose(0,2,1,3,4).reshape(bh*4,bw*4,3)
