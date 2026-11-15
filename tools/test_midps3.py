import sys,glob,os; sys.path.insert(0,os.path.dirname(__file__)); import midps3
songs=sys.argv[1]; ok=rt=0; rep=[]
for f in sorted(glob.glob(songs+'/*/*.mid_ps3')):
    b=open(f,'rb').read(); d=midps3.read(b)
    rt+=midps3.write(d)==b
    c=midps3.compile_mid(f[:-4])
    if c==b: ok+=1
    else:
        i=next((i for i in range(min(len(b),len(c))) if b[i]!=c[i]),min(len(b),len(c)))
        rep.append('%s len %d vs %d first diff @%d %s'%(os.path.basename(f),len(b),len(c),i,'(tail)' if i>=d['tail_offset'] else ''))
n=len(glob.glob(songs+'/*/*.mid_ps3'))
print('read/write round trip: %d/%d'%(rt,n)); print('compile from .mid exact: %d/%d'%(ok,n)); print('\n'.join(rep))
