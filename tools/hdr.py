import sys,struct
d=open(sys.argv[1],'rb').read()
def rnd(k):
    r=(k-((k//0x1F31D)*0x1F31D))*0x41A7-(k//0x1F31D)*0xB14
    if r<=0: r+=0x7FFFFFFF
    return r
def dec(d,end,x):
    k=struct.unpack(end+'i',d[:4])[0]; out=bytearray(d[4:])
    for i in range(len(out)):
        k=rnd(k); out[i]^=(k&0xff)^x
    return bytes(out)
if len(sys.argv)>2:
    end,x=sys.argv[2],int(sys.argv[3]); open(sys.argv[4],'wb').write(dec(d,end,x)); sys.exit()
for end in '<>':
    for x in (0,0xff):
        o=dec(d[:68],end,x); print(end,x,o[:32].hex(),struct.unpack('>I',o[:4])[0],struct.unpack('<I',o[:4])[0])
