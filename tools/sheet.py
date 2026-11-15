import sys,os,glob
from PIL import Image,ImageDraw
fs=sorted(glob.glob(sys.argv[1]+'/*.png')); out=sys.argv[2]; os.makedirs(out,exist_ok=True)
T=160;C=8;R=6;per=C*R
for s in range(0,len(fs),per):
    sh=Image.new('RGB',(C*T,R*(T+14)),(40,0,40)); dr=ImageDraw.Draw(sh)
    for i,f in enumerate(fs[s:s+per]):
        im=Image.open(f).convert('RGB'); im.thumbnail((T,T))
        x,y=(i%C)*T,(i//C)*(T+14); sh.paste(im,(x,y))
        dr.text((x+2,y+T),os.path.basename(f).replace('.png','')[-26:],fill=(255,255,0))
    sh.save(f'{out}/sheet_{s//per:02d}.png')
print(len(fs))
