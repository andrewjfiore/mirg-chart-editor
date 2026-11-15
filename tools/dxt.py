import sys,struct
from PIL import Image
def dxt1(data,w,h):
    img=Image.new('RGB',(w,h)); px=img.load(); p=0
    def c565(c): return ((c>>11&31)*255//31,(c>>5&63)*255//63,(c&31)*255//31)
    for by in range(0,h,4):
        for bx in range(0,w,4):
            c0,c1,bits=struct.unpack_from('<HHI',data,p); p+=8
            a,b=c565(c0),c565(c1)
            if c0>c1: cols=[a,b,tuple((2*x+y)//3 for x,y in zip(a,b)),tuple((x+2*y)//3 for x,y in zip(a,b))]
            else: cols=[a,b,tuple((x+y)//2 for x,y in zip(a,b)),(0,0,0)]
            for i in range(16):
                px[bx+i%4,by+i//4]=cols[bits>>(2*i)&3]
    return img
f,w,h,out=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]
d=open(f,'rb').read()
tot=0;ww,hh=w,h
while ww>=1 and hh>=1:
    tot+=max(1,ww//4)*max(1,hh//4)*8; ww//=2; hh//=2
off=len(d)-tot; print('header',off)
dxt1(d[off:],w,h).save(out)
