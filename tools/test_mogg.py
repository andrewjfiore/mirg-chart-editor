import sys,glob,os; sys.path.insert(0,os.path.dirname(__file__)); import mogg
fs=sorted(glob.glob(sys.argv[1]+'/*/*.mogg')); ok=0; bad=[]
for f in fs:
    b=open(f,'rb').read(); h=mogg.parse(b)
    if mogg.build(b[h['ogg_offset']:],h['buffer'])==b: ok+=1
    else: bad.append(os.path.basename(f))
print('mogg rebuild exact: %d/%d'%(ok,len(fs)),bad[:5])
