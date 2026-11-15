"""Ogg Vorbis packet timing without decoding (mode/blocksize parse as in FFmpeg vorbis_parser)."""
import struct
def packets(o):
    """Yield (packet_bytes, start_byte_of_page_where_packet_begins, end_byte_offset)."""
    p=0; cur=b''; cur_start=None
    while p+27<=len(o):
        nseg=o[p+26]; segs=o[p+27:p+27+nseg]; q=p+27+nseg
        for s in segs:
            if cur_start is None: cur_start=p
            cur+=o[q:q+s]; q+=s
            if s<255: yield cur,cur_start,q; cur=b''; cur_start=None
        p=q
def ilog(v):
    n=0
    while v: n+=1; v>>=1
    return n
def mode_flags(setup):
    bits=[]
    for byte in reversed(setup):
        for i in range(7,-1,-1): bits.append((byte>>i)&1)
    i=0
    while bits[i]==0: i+=1
    i+=1  # framing bit
    def take(n):
        nonlocal i
        v=0
        for k in range(n): v=(v<<1)|bits[i+k]
        i+=n; return v
    count=0; last=0; start=i
    while len(bits)-i>=97:
        if take(8)>63 or take(16) or take(16): break
        take(1); count+=1
        j=i; v=0
        for k in range(6): v=(v<<1)|bits[j+k]
        # bits are reversed: the 6-bit field read backwards
        vv=v
        if vv+1==count: last=count
        if count>64: break
    i=start; flags=[]
    for _ in range(last):
        take(8); take(16); take(16); flags.append(take(1))
    return list(reversed(flags))
def timeline(o):
    """Return list of (packet_end_byte, packet_begin_page_byte, sample_end) for audio packets."""
    it=packets(o); ident=next(it)[0]; next(it); setup=next(it)[0]
    bs0=1<<(ident[28]&0x0F); bs1=1<<(ident[28]>>4)
    flags=mode_flags(setup); mbits=ilog(len(flags)-1); prev=None; pos=0; out=[]
    for pk,pstart,end in it:
        if not pk or pk[0]&1: continue
        mode=(pk[0]>>1)&((1<<mbits)-1); bs=bs1 if flags[mode] else bs0
        if prev is not None: pos+=prev//4+bs//4
        prev=bs; out.append((end,pstart,pos))
    return out,(bs0,bs1,flags)
