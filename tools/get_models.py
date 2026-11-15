"""Download the trained charting models from the project's GitHub release. The launchers run this on every start;
it only downloads what is missing, so a model you trained yourself is never replaced."""
import hashlib, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://github.com/andrewjfiore/mirg-chart-editor/releases/download/models-v1/'
FILES = {
    'charter.pt': '063ee0024d37109c26666a3e2f31f9839cd9a15149bea11c801b14bf556415e1',
    'weightspace_weights.npz': 'a4cc9f26fa2fde02bc78e452c0b18eb38dc2f697161e479a0b7e5e888c735b74',
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


for name, want in FILES.items():
    dst = os.path.join(ROOT, 'ml', name)
    if os.path.exists(dst):
        continue
    print('Downloading the charting model', name)
    tmp = dst + '.part'
    urllib.request.urlretrieve(BASE + name, tmp)
    if sha256(tmp) != want:
        sys.exit('The download of %s came out different from the release. Start the app again to retry.' % name)
    os.replace(tmp, dst)
