import sys,os,struct,glob,numpy as np
from PIL import Image
sys.path.insert(0,os.path.dirname(__file__))
from texlib import dxt_color,tile
out=sys.argv[2]; os.makedirs(out,exist_ok=True); bad=[]
for f in glob.glob(sys.argv[1]+'/**/*_ps3',recursive=True):
    if not (f.endswith('.png_ps3') or f.endswith('.bmp_ps3')): continue
    d=open(f,'rb').read(); tab=None
    for o in [0xb0]+list(range(0x60,min(0x300,len(d)-16),4)):
        n,w,h,one=struct.unpack_from('>IIII',d,o)
        if 1<=n<=14 and one==1 and 1<=w<=4096 and (w&(w-1))==0: tab=(o,n,w,h);break
    if not tab: bad.append(f);continue
    o,n,w,h=tab; end=o+4+12*n; size=struct.unpack_from('>I',d,end+4)[0]; p=end+8
    raw=np.frombuffer(d[p:p+size],np.uint8); bpp=size*8//(w*h) if w*h else 0
    try:
        if bpp==4: nb=size//8; img=tile(dxt_color(raw.reshape(nb,8)),w,h)
        elif bpp==8: nb=size//16; img=tile(dxt_color(raw.reshape(nb,16)[:,8:]),w,h)
        elif bpp==32: img=raw.reshape(h,w,4)[:,:,1:4]
        else: bad.append(f+' bpp%d'%bpp); continue
        Image.fromarray(img.astype(np.uint8)).save(os.path.join(out,f.split('/ps3/')[1].replace('/','__')+'.png'))
    except Exception as e: bad.append(f+' '+str(e))
print('bad',len(bad)); [print(b.split('/ps3/')[1]) for b in bad[:30]]
