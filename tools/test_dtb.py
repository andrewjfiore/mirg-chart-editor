import sys,glob,os; sys.path.insert(0,os.path.dirname(__file__)); import dtb
root=sys.argv[1]; fs=glob.glob(root+'/**/*dta_ps3',recursive=True); rt=0
for f in fs:
    b=open(f,'rb').read(); rt+=dtb.write(dtb.read(b))==b
print('binary read/write round trip: %d/%d'%(rt,len(fs)))
ok=0; bad=[]; ms=glob.glob(root+'/**/*.moggsong',recursive=True)
for f in ms:
    ship=open(f+'_dta_ps3','rb').read(); mine=dtb.compile_text(open(f,encoding='latin-1').read())
    if mine==ship: ok+=1
    else:
        i=next((i for i in range(min(len(ship),len(mine))) if ship[i]!=mine[i]),min(len(ship),len(mine))); bad.append('%s len %d/%d diff@%d ship %s mine %s'%(os.path.basename(f),len(ship),len(mine),i,ship[i-6:i+10].hex(),mine[i-6:i+10].hex()))
print('text compile exact: %d/%d'%(ok,len(ms))); print('\n'.join(bad[:8]))
