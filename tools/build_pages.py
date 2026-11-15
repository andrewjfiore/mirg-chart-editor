"""Build the GitHub Pages site: the editor and play test with pages/static-api.js answering their /api calls.

usage: python3 tools/build_pages.py [OUT_DIR]   (default: site/)
Only the files listed in SITE are written, so no game data can end up in the site.
"""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = '<script src="static-api.js"></script>\n'
SITE = ('index.html', 'play.html', 'static-api.js', '.nojekyll')


def page(name):
    s = open(os.path.join(ROOT, 'editor', name), encoding='utf-8').read()
    i = s.find('<script>')  # the page's own script; the stand-in must load first
    if i < 0:
        raise SystemExit('no <script> in editor/' + name)
    return s[:i] + TAG + s[i:]


def build(out):
    os.makedirs(out, exist_ok=True)
    for name in ('index.html', 'play.html'):
        open(os.path.join(out, name), 'w', encoding='utf-8').write(page(name))
    shutil.copyfile(os.path.join(ROOT, 'pages', 'static-api.js'), os.path.join(out, 'static-api.js'))
    open(os.path.join(out, '.nojekyll'), 'w').close()
    extra = sorted(set(os.listdir(out)) - set(SITE))
    if extra:
        raise SystemExit('unexpected files in %s: %s' % (out, ', '.join(extra)))
    return out


if __name__ == '__main__':
    out = build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'site'))
    for name in SITE:
        p = os.path.join(out, name)
        assert os.path.exists(p), p
    assert open(os.path.join(out, 'index.html'), encoding='utf-8').read().count('static-api.js') == 1
    print('built', out)
