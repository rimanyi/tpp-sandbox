"""Build the MkDocs source tree (docs/) from the data files and the hand-written content.

    python scripts/build_site.py        # writes docs/, then run:  mkdocs build   (or: mkdocs serve)

Inputs (the things a maintainer edits):
  data/catalog/contact.yaml   catalog of contact singularities
  data/catalog/multi.yaml     extra text for special multi-singularities
  data/catalog/lac.txt        Large Algebra Collider splittings
  data/contact/<ID>/*.txt     data files of mono-singularities
  data/multi/<ID>/*.txt       data files of multi-singularities
  content/**                  prose pages (Markdown), styles, scripts
  files/                      PDFs, images and other downloads
Output: docs/  (generated, never edited by hand; not stored in git)
"""
import html
import os
import posixpath
import re
import shutil
import sys
import zipfile
from collections import defaultdict, OrderedDict

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tpplib import (read_datafile, mono_tex, mono_plain, mono_html, multi_parts, multi_tex,  # noqa: E402
                    multi_html, multi_slug, max_tdeg)

ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
OLD_SITE = 'https://tpp.web.unc.edu/'

# ====================================================================== load inputs
CAT = OrderedDict((e['id'], e) for e in yaml.safe_load(open(os.path.join(ROOT, 'data/catalog/contact.yaml'), encoding='utf-8')))
MCAT = {e['id']: e for e in (yaml.safe_load(open(os.path.join(ROOT, 'data/catalog/multi.yaml'), encoding='utf-8')) or [])}
LAC = [ln.strip() for ln in open(os.path.join(ROOT, 'data/catalog/lac.txt'), encoding='utf-8') if '->' in ln and not ln.startswith('#')]
OLD_URLS = yaml.safe_load(open(os.path.join(ROOT, 'data/catalog/old-urls.yaml'), encoding='utf-8'))
ATTACH = {}
att_file = os.path.join(ROOT, 'migration', 'attachments.txt')
if os.path.exists(att_file):
    for u in open(att_file, encoding='utf-8').read().split():
        ATTACH[posixpath.basename(u)] = u
ORDER = {mid: i for i, mid in enumerate(CAT)}


class Cell:
    def __init__(self, entity, fname, header, assigns, path):
        self.entity, self.fname, self.h, self.a, self.path = entity, fname, header, assigns, path
        self.kind = header.get('kind', '')
        self.l = int(header['l']) if header.get('l', '').strip().lstrip('-').isdigit() else None
        self.version = 'v2025-04' if '.v2025-04' in fname else None
        self.singleton_multi = fname.startswith('multi_')
        m = re.match(r'\s*(-?\d+)', header.get('codimension', ''))
        self.codim = int(m.group(1)) if m else None
        d = header.get('computed-up-to-degree', '').strip()
        self.degree = int(d) if d.isdigit() else None

    def get(self, suffix):
        for n, e, s in self.a:
            if n.endswith(suffix):
                return e
        return None

    @property
    def rel(self):           # path under docs/
        return posixpath.join('data', os.path.relpath(self.path, os.path.join(ROOT, 'data')).replace(os.sep, '/'))

    @property
    def empty(self):
        return not self.a


CELLS = defaultdict(list)    # entity id -> [Cell]
MULTI = set()
for top in ('contact', 'multi'):
    base = os.path.join(ROOT, 'data', top)
    if not os.path.isdir(base):
        continue
    for eid in sorted(os.listdir(base)):
        for fn in sorted(os.listdir(os.path.join(base, eid))):
            if fn.endswith('.txt'):
                p = os.path.join(base, eid, fn)
                h, a = read_datafile(p)
                CELLS[eid].append(Cell(eid, fn, h, a, p))
        if top == 'multi':
            MULTI.add(eid)


def cells(eid, kind=None, singleton=None, version=False):
    out = [c for c in CELLS.get(eid, []) if (kind is None or c.kind == kind)]
    if singleton is not None:
        out = [c for c in out if c.singleton_multi == singleton]
    if version is not None:
        out = [c for c in out if (c.version is not None) == bool(version)]
    return sorted(out, key=lambda c: (c.l if c.l is not None else -1))


def entity_key(eid):
    if eid in ORDER:
        return (0, ORDER[eid], '')
    parts = multi_parts(eid)
    return (1, sum(k for k, _ in parts), tuple(sorted((-ORDER.get(n, 99), k) for k, n in parts)), eid)


MULTI_IDS = sorted(MULTI, key=lambda e: (e != 'EMPTY', entity_key(e)))

# ====================================================================== paths and links
PAGES = {}   # docs-relative .md path -> text


def mono_page(mid):
    return f'singularities/contact/{mid}.md'


def multi_page(eid):
    return f'singularities/multi/{multi_slug(eid)}.md'


def page_of(eid):
    return multi_page(eid) if eid in MULTI else mono_page(eid)


def url_dir(md):
    """URL directory of a page (use_directory_urls)."""
    d = md[:-3]
    if d == 'index':
        return ''
    if d.endswith('/index'):
        return d[:-6]
    return d


def rel_url(from_md, to):
    """Relative URL from page from_md to a page (.md) or a file under docs/."""
    src = url_dir(from_md)
    if to.endswith('.md'):
        tgt = url_dir(to)
        r = posixpath.relpath(tgt or '.', src or '.')
        return ('' if r == '.' else r) + '/' if r != '.' else './'
    return posixpath.relpath(to, src or '.')


def rel_md(from_md, to_md):
    return posixpath.relpath(to_md, posixpath.dirname(from_md) or '.')


def esc(s):
    return html.escape(str(s), quote=False)


def attr(s):
    return html.escape(str(s), quote=True)


def name_html(eid):
    return multi_html(eid) if eid in MULTI else mono_html(eid)


def name_tex(eid):
    if eid in MULTI:
        return multi_tex(eid)
    e = CAT.get(eid, {})
    return e.get('tex') or mono_tex(eid)


def elink(cur, eid, anchor=''):
    if eid in CAT or eid in MULTI:
        return f'<a href="{rel_url(cur, page_of(eid))}{anchor}">{name_html(eid)}</a>'
    return name_html(eid)


def file_link(cur, c, label=None):
    return (f'<a class="tpp-file" href="{attr(rel_url(cur, c.rel))}" title="plain-text data file, readable by Maple">'
            f'{esc(label or c.fname)}</a>')


def M(tex):
    return r'\(' + esc(tex) + r'\)'


def maple_to_tex(s):
    s = re.sub(r'\s+', ' ', s.strip())
    s = re.sub(r'^\+\s*', '', s)
    s = re.sub(r'c\[(\d+)\]', r'c_{\1}', s)
    s = re.sub(r's\[\[([\d, ]*)\]\]', lambda m: 's_{' + (m.group(1).replace(' ', '') or r'\varnothing') + '}', s)
    s = re.sub(r'(\d+)/(\d+)\*', r'\\tfrac{\1}{\2}\\,', s)
    s = re.sub(r'\^(\d+)', r'^{\1}', s)
    s = s.replace('*', r'\,').replace('( ', '(').replace(' )', ')')
    return s


def pre(s, cls='maple'):
    return f'<pre class="{cls}" data-search-exclude>{esc(s)}</pre>'


def prov(c, cur):
    src = c.h.get('source', '')
    bits = []
    if src:
        todo = 'to be added' in src
        bits.append('Source: ' + (esc(src) if not todo else 'not recorded yet <span class="tpp-todo">to add</span>'))
    rf = c.h.get('retrieved-from', '')
    m = re.match(r'(\S+)\s*\(page modified ([\d-]+)\)', rf)
    if m:
        slug = m.group(1).rstrip('/').split('/')[-1]
        bits.append(f'migrated from the old page <a href="{attr(m.group(1))}">{esc(slug)}</a> ({m.group(2)})')
    return '<p class="tpp-prov">' + ' · '.join(bits) + '</p>'


def note_html(c):
    n = c.h.get('note')
    if not n:
        return ''
    cls = 'tpp-note tpp-warn' if 'DISAGREE' in n or 'could not' in n else 'tpp-note'
    return f'<p class="{cls}">' + esc(n).replace('\n', '<br>') + '</p>'


def fix_root(md_path, text):
    up = rel_url(md_path, 'index.md')
    up = '' if up == './' else up.rstrip('/')
    text = text.replace('@ROOT@/', (up + '/') if up else './')
    text = text.replace('@ROOT@', up or '.')
    mdup = posixpath.relpath('.', posixpath.dirname(md_path) or '.')
    text = text.replace('@MD@/', '' if mdup == '.' else mdup + '/')

    # attachments: link to the local copy if it exists in files/, else to the old site
    def att(m):
        name = m.group(1)
        if os.path.exists(os.path.join(ROOT, 'files', name)):
            return m.group(0)
        return ATTACH.get(name) or (OLD_SITE + 'wp-content/uploads/sites/17537/' + name)
    text = re.sub(r'(?:\.\./)*(?:\./)?files/([^"\s<>)]+)', att, text)
    return text


def front(title, extra=None):
    fm = {'title': title}
    if extra:
        fm.update(extra)
    return '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + '---\n\n'

# ====================================================================== entity pages: mono


def known_grid(cur, eid):
    rows = []
    groups = [('tp', 'Thom polynomial', '#tp'), ('ssm', 'SSM-Thom polynomial', '#ssm'), ('ktp', 'K-theoretic Thom polynomial', '#ktp')]
    target = cells(eid, 'target_ssm', singleton=True)
    source = cells(eid, 'source_ssm', singleton=True)
    ls = sorted({c.l for g in groups for c in cells(eid, g[0])} | {c.l for c in target + source})
    if not ls:
        return ''
    ls = list(range(min(ls), max(ls) + 1))

    def cell_mark(c, anchor):
        if c is None:
            return '<span class="tpp-no">—</span>'
        if c.degree:
            return f'<a class="tpp-deg" href="{anchor}" title="computed up to cohomological degree {c.degree}">≤ {c.degree}</a>'
        return f'<a href="{anchor}">✓</a>'
    head = ''.join(f'<th>l = {l}</th>' for l in ls) + '<th>all l</th>'
    for kind, label, anc in groups:
        by_l = {c.l: c for c in cells(eid, kind)}
        if not by_l and kind != 'tp':
            continue
        allcol = '<span class="tpp-no">—</span>'
        if kind == 'tp':
            s = cells(eid, 'series')
            if s and not s[0].empty:
                allcol = '<a href="#series">Thom series ✓</a>'
            elif s:
                allcol = '<a href="#series"><span class="tpp-soon">placeholder</span></a>'
        if kind == 'ssm':
            allcol = '<span class="tpp-no">not known</span>'
        tds = ''.join(f'<td>{cell_mark(by_l.get(l), f"{anc}-l{l}")}</td>' for l in ls)
        rows.append(f'<tr><td><a href="{anc}">{label}</a></td>{tds}<td>{allcol}</td></tr>')
    for prep in CAT.get(eid, {}).get('in_preparation', []) or []:
        rows.append(f'<tr><td>{esc(prep.split(" (")[0])}</td>' + ''.join('<td><span class="tpp-no">—</span></td>' for _ in ls)
                    + '<td><span class="tpp-soon">in preparation</span></td></tr>')
    for lst, label, anc in ((target, 'Target SSM, as multi-singularity', '#mt'), (source, 'Source SSM, as multi-singularity', '#ms')):
        if lst:
            by_l = {c.l: c for c in lst}
            rows.append(f'<tr><td><a href="#multi">{label}</a></td>' + ''.join(f'<td>{cell_mark(by_l.get(l), f"{anc}-l{l}")}</td>' for l in ls) + '<td><span class="tpp-no">—</span></td></tr>')
    return ('<div class="tpp-tablewrap"><table class="tpp-known">'
            f'<thead><tr><th>Object</th>{head}</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>\n'
            '<p class="tpp-legend">✓ known · ≤ d computed up to cohomological degree d · — nothing recorded (unknown, or not yet entered). '
            'Generated from the data files.</p>')


def tp_cell(cur, c, eid):
    mono, schur = c.get('_monomial'), c.get('_schur')
    parts = [f'<div class="tpp-cell" id="tp-l{c.l}"><div class="tpp-cell-head"><span class="tpp-cell-title">l = {c.l}</span>'
             f'<span class="tpp-meta">codimension {c.codim}</span>{file_link(cur, c)}</div>']
    if c.h.get('note'):
        parts.append(note_html(c))
    for lab, e in (('Monomial basis', mono), ('Schur basis', schur)):
        if e:
            parts.append(f'<div class="tpp-lbl">{lab}</div>')
            if len(e) < 500:
                parts.append(f'<div class="tpp-math">{M(maple_to_tex(e))}</div>')
    parts.append('<div class="tpp-lbl">Maple</div>' + pre('\n'.join(x for x in (mono, schur) if x)))
    parts.append(prov(c, cur) + '</div>')
    return ''.join(parts)


def details_cell(cur, c, anchor, title, meta, body, open_=False):
    return (f'<details class="tpp-cell" id="{anchor}"{" open" if open_ else ""}><summary><span class="tpp-cell-title">{title}</span>'
            f'<span class="tpp-meta">{meta}</span>{file_link(cur, c)}</summary>{note_html(c)}{body}{prov(c, cur)}</details>')


def series_block(cur, c):
    out = []
    h = c.h
    meta = []
    if h.get('tp-degree'):
        meta.append('Tp degree ' + M(h['tp-degree']))
    if h.get('local-algebra'):
        meta.append('local algebra ' + esc(h['local-algebra']))
    out.append(f'<div class="tpp-cell" id="series-cell"><div class="tpp-cell-head"><span class="tpp-cell-title">Thom series</span>'
               f'<span class="tpp-meta">{" · ".join(meta)}</span>{file_link(cur, c)}</div>')
    i = 1
    while f'profile-{i}' in h:
        out.append(f'<div class="tpp-lbl">Residue presentation, profile {M(h[f"profile-{i}"])}</div>')
        disp = c.get(f'_profile{i}_display')
        if disp:
            out.append(f'<div class="tpp-math">{esc(disp)}</div>')
        boxes = [(n, e) for n, e, s in c.a if re.search(rf'_profile{i}(_\d+)?$', n) and n.startswith('F_')]
        for j, (n, e) in enumerate(boxes, 1):
            lab = h.get(f'box-{i}-{j}', 'Maple expression')
            out.append(f'<div class="tpp-sublbl">{esc(lab)}</div>' + pre(e))
        i += 1
    ex = c.get('_explicit_tex')
    if ex:
        out.append('<div class="tpp-lbl">Explicit Thom series</div><div class="tpp-math">'
                   + M(r'\displaystyle \mathrm{Ts} = ' + ex) + '</div>')
    if h.get('note'):
        out.append('<p class="tpp-note">' + esc(h['note']).replace('\n', '<br>') + '</p>')
    out.append(f'<p class="tpp-note">{esc(h.get("convention", ""))}</p>' if h.get('convention') else '')
    out.append(prov(c, cur) + '</div>')
    return ''.join(out)


def lac_for(eid):
    own, arises, inside = [], [], []
    pat = re.compile(r'(?<![A-Za-z0-9])' + re.escape(eid) + r'(?![A-Za-z0-9])')
    for ln in LAC:
        lhs, _, rhs = ln.partition('->')
        if lhs.strip() == eid:
            own.append(ln)
        elif pat.search(rhs):
            # does eid occur as a whole product, i.e. a splitting INTO eid alone?
            if any(re.fullmatch(r'\s*' + re.escape(eid) + r'\s*(\(.*\))?\s*', p) for p in re.split(r',|---', rhs)):
                arises.append(ln)
            else:
                inside.append(ln)
    return own, arises, inside


def linkify_rule(cur, ln):
    def rep(m):
        tok = m.group(0)
        if tok in CAT:
            return elink(cur, tok)
        return esc(tok)
    return re.sub(r'(?<![A-Za-z0-9])([A-Z]+\d+)(?![A-Za-z0-9])', rep, esc(ln).replace('-&gt;', '→'))


def mono_page_text(mid):
    cur = mono_page(mid)
    e = CAT[mid]
    out = [front(mono_plain(mid)), f'<div class="tpp-eyebrow">Contact mono-singularity'
           + (" · Mather's list" if e.get('mather') else ' · outside Mather\'s list')
           + (f' · <span class="tpp-nt">μ</span> = {e["mu"]}' if e.get('mu') is not None else '') + '</div>\n\n',
           f'# ${name_tex(mid)}$\n\n']
    facts = []
    if e.get('ideal'):
        alg = e['ideal']
        facts.append(('Local algebra', ('ideal ' + esc(alg)) + (('<br><span class="tpp-meta">also written ' + esc(', '.join(e['ideal_alternatives'])) + '</span>') if e.get('ideal_alternatives') else '')))
    if e.get('mu') is not None:
        facts.append(('Milnor number <span class="tpp-nt">μ</span>', str(e['mu'])))
    if e.get('tb_class') or e.get('sigma'):
        tb = e.get('tb_class') or e.get('sigma')
        open_in = any('open in its Thom-Boardman' in r for r in e.get('remarks', []) or [])
        facts.append(('Thom–Boardman class', M(tb) + (' <span class="tpp-meta">(open in it)</span>' if open_in else '')))
    if e.get('codim'):
        facts.append(('Codimension', M(e['codim'])))
    if e.get('l_range'):
        facts.append(('In the nice range for', esc(e['l_range'])))
    if e.get('d'):
        facts.append(('d-sequence', 'd = ' + esc(e['d']) + ' <span class="tpp-meta">(d<sub>i</sub> = dim m<sup>i</sup>/m<sup>i+1</sup>)</span>'))
    if e.get('suggested_name'):
        facts.append(('Also called', M(e['suggested_name'])))
    if facts:
        out.append('<dl class="tpp-facts">' + ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts) + '</dl>\n\n')

    tp = cells(mid, 'tp')
    series = cells(mid, 'series')
    ssm = cells(mid, 'ssm')
    ktp = cells(mid, 'ktp')
    mt = cells(mid, 'target_ssm', singleton=True, version=None)
    msrc = cells(mid, 'source_ssm', singleton=True)
    grid = known_grid(cur, mid)
    out.append('## What is known\n\n')
    out.append((grid if grid else '<p>No Thom polynomial data is recorded for this singularity yet.</p>') + '\n\n')

    if tp:
        out.append('## Thom polynomials {#tp}\n\nOrdinary Thom polynomials in cohomology, one for each relative dimension $l$, '
                   'in the quotient Chern classes $c_i$ and in the Schur basis $s_\\lambda$ '
                   f'(see [Conventions]({rel_md(cur, "background/conventions.md")})).\n\n')
        out.append('\n'.join(tp_cell(cur, c, mid) for c in tp) + '\n\n')
    if series:
        out.append(f'## Thom series {{#series}}\n\nAll relative dimensions at once; conventions are explained on the '
                   f'[Thom series page]({rel_md(cur, "tables/thom-series.md")}).\n\n')
        out.append(series_block(cur, series[0]) + '\n\n')
    if ssm:
        out.append('## SSM-Thom polynomials {#ssm}\n\nThe Segre–Schwartz–MacPherson Thom polynomial is an infinite series whose lowest-degree '
                   'part is the Thom polynomial; $t$ records the cohomological degree. Each is known only up to the stated degree.\n\n')
        for i, c in enumerate(ssm):
            body = '<div class="tpp-lbl">Monomial basis</div>' + pre(c.get('_monomial') or '')
            if c.get('_schur'):
                body += '<div class="tpp-lbl">Schur basis</div>' + pre(c.get('_schur'))
            out.append(details_cell(cur, c, f'ssm-l{c.l}', f'l = {c.l}', f'codimension {c.codim} · up to degree {c.degree}', body, open_=(i == 0)) + '\n')
        out.append('\n')
    if ktp:
        out.append('## K-theoretic Thom polynomials {#ktp}\n\nK-theoretic fundamental class: the class of the structure sheaf of a resolution, '
                   'pushed forward; written in the Grothendieck expansion $g_\\lambda$. Stored in TeX-like notation for now '
                   '(to be normalised to Maple syntax).\n\n')
        for c in ktp:
            t = c.get('_tex') or ''
            out.append(f'<div class="tpp-cell" id="ktp-l{c.l}"><div class="tpp-cell-head"><span class="tpp-cell-title">l = {c.l}</span>'
                       f'<span class="tpp-meta">codimension {c.codim}</span>{file_link(cur, c)}</div>'
                       f'<div class="tpp-math">{M(t)}</div>{prov(c, cur)}</div>\n')
        out.append('\n')
    for prep in e.get('in_preparation', []) or []:
        out.append(f'## {prep.split(" (")[0]}\n\nNot on the portal yet; in preparation ({esc(prep.split(" (", 1)[1].rstrip(")")) if " (" in prep else ""}). '
                   'When the data file appears in the repository, this section and the grid above fill in automatically.\n\n')
    if mt or msrc:
        out.append(f'## As a multi-singularity {{#multi}}\n\nA single {name_html(mid)} point is also a multi-singularity. Its target and source SSM '
                   f'polynomials use the pushforward notation of the [Conventions]({rel_md(cur, "background/conventions.md")}) page.\n\n')
        for c in mt:
            v = ' (older version, April 2025)' if c.version else ''
            anc = f'mt-l{c.l}' + ('-old' if c.version else '')
            out.append(details_cell(cur, c, anc, f'Target SSM, l = {c.l}{v}', f'target codimension {c.codim} · up to degree {c.degree}', pre(c.a[0][1])) + '\n')
        for c in msrc:
            out.append(details_cell(cur, c, f'ms-l{c.l}', f'Source SSM (R-)polynomial, l = {c.l}', f'source codimension {c.codim} · up to degree {c.degree}', pre(c.a[0][1])) + '\n')
        out.append('\n')

    # relations
    own, arises, inside = lac_for(mid)
    containing = [m for m in MULTI_IDS if any(n == mid for _, n in multi_parts(m))]
    rel = []
    if own or arises:
        rel.append('### Elementary splittings (Large Algebra Collider)\n\n<ul class="tpp-rules">'
                   + ''.join(f'<li>{linkify_rule(cur, ln)} <span class="tpp-meta">— splittings of {name_html(mid)}</span></li>' for ln in own)
                   + ''.join(f'<li>{linkify_rule(cur, ln)} <span class="tpp-meta">— {name_html(mid)} arises from {linkify_rule(cur, ln.split("->")[0].strip())}</span></li>' for ln in arises)
                   + '</ul>\n\n')
    if inside:
        rel.append(f'<p class="tpp-meta">{name_html(mid)} also occurs inside the splittings of '
                   + ', '.join(linkify_rule(cur, ln.split('->')[0].strip()) for ln in inside) + '.</p>\n\n')
    if containing:
        rel.append(f'### Multi-singularities with data that contain {name_html(mid)}\n\n<ul class="tpp-cols">'
                   + ''.join(f'<li>{elink(cur, m)}</li>' for m in containing) + '</ul>\n\n')
    if e.get('symmetry_record'):
        rel.append(f'### Symmetry record\n\n{pre(e["symmetry_record"])}\n<p class="tpp-meta">From the '
                   f'<a href="{rel_url(cur, "local-algebras/symmetries.md")}">symmetries page</a>; the fields are to be documented there.</p>\n\n')
    rel.append(f'### Hierarchy\n\nAdjacencies are currently drawn in the charts on the [hierarchy page]({rel_md(cur, "local-algebras/hierarchy.md")}). '
               'Once adjacency is entered as data, the neighbours of this singularity will be listed here.\n\n')
    out.append('## Relations to other singularities {#rel}\n\n' + ''.join(rel))

    notes = list(e.get('notes', []) or []) + [r for r in (e.get('remarks') or []) if 'open in its Thom-Boardman' not in r]
    if notes:
        out.append('## Notes\n\n<ul>' + ''.join(f'<li>{esc(n)}</li>' for n in notes) + '</ul>\n\n')
    out.append(data_footer(cur, mid))
    return ''.join(out)


def data_footer(cur, eid):
    cs = sorted(CELLS.get(eid, []), key=lambda c: c.fname)
    if not cs:
        return ('<div class="tpp-footer"><p>There are no data files for this singularity yet. Adding one under '
                f'<code>data/contact/{esc(eid)}/</code> (for example <code>tp_l0.txt</code>) makes it appear here and in the tables.</p></div>\n')
    return ('<div class="tpp-footer"><p>This page is generated from the catalog and from ' + str(len(cs)) + ' data files:</p><ul class="tpp-cols tpp-files">'
            + ''.join(f'<li>{file_link(cur, c)}</li>' for c in cs) + '</ul></div>\n')

# ====================================================================== entity pages: multi


def multi_page_text(eid):
    cur = multi_page(eid)
    parts = multi_parts(eid)
    out = [front(multi_html(eid).replace('<sub>', '').replace('</sub>', '')),
           '<div class="tpp-eyebrow">Contact multi-singularity' + (' · the empty one' if eid == 'EMPTY' else f' · {sum(k for k, _ in parts)} points') + '</div>\n\n',
           f'# ${multi_tex(eid)}$\n\n']
    desc = MCAT.get(eid, {}).get('description')
    if desc:
        out.append(desc + '\n\n')
    facts = []
    if parts:
        facts.append(('Points', ', '.join((f'{k} × ' if k > 1 else '') + elink(cur, n) for k, n in parts)))
    cods = sorted({(c.l, c.h.get('codimension', '')) for c in CELLS[eid] if c.l is not None and c.kind != 's0'})
    if cods:
        facts.append(('Codimension', '<br>'.join(f'l = {l}: {esc(cd)}' for l, cd in cods)))
    if facts:
        out.append('<dl class="tpp-facts">' + ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts) + '</dl>\n\n')
    # grid
    kinds = [('s0', 'S₀ series = log MS(l)', 's0'), ('target_ssm', 'Target SSM polynomial', 'mt'), ('source_ssm', 'Source SSM (R-)polynomial', 'ms')]
    ls = sorted({c.l for c in CELLS[eid] if c.l is not None})
    rows = []
    for kind, label, anc in kinds:
        by_l = {c.l: c for c in cells(eid, kind)}
        if not by_l:
            continue
        rows.append(f'<tr><td>{label}</td>' + ''.join(
            (f'<td><a class="tpp-deg" href="#{anc}-l{l}">≤ {by_l[l].degree}</a></td>' if l in by_l else '<td><span class="tpp-no">—</span></td>') for l in ls) + '</tr>')
    out.append('## What is known\n\n<div class="tpp-tablewrap"><table class="tpp-known"><thead><tr><th>Object</th>'
               + ''.join(f'<th>l = {l}</th>' for l in ls) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>\n'
               '<p class="tpp-legend">≤ d: computed up to cohomological degree d. Generated from the data files.</p>\n\n')
    s0 = cells(eid, 's0')
    if s0:
        intro = MCAT.get(eid, {}).get('s0_intro', '')
        out.append('## S₀ series {#s0}\n\n' + (('<div class="tpp-note">' + esc(intro).replace('\n', '<br>') + '</div>\n\n') if intro else ''))
        for i, c in enumerate(s0):
            body = '<div class="tpp-lbl">Monomial (pushforward) basis</div>' + pre(c.get('_monomial') or '') \
                   + '<div class="tpp-lbl">Schur (pushforward) basis</div>' + pre(c.get('_schur') or '')
            out.append(details_cell(cur, c, f's0-l{c.l}', f'l = {c.l}', f'up to degree {c.degree}', body, open_=(i == 0)) + '\n')
        out.append(f'\n### Consequences\n\nThe [image Milnor numbers]({rel_md(cur, "derived/image-milnor-numbers.md")}) of quasihomogeneous germs '
                   'follow from the S₀ data.\n\n')
    tg = cells(eid, 'target_ssm', version=None)
    if tg:
        out.append('## Target SSM polynomials {#target}\n\n' + ('For the empty multi-singularity this is the master series MS(l) = exp S₀(l).\n\n' if eid == 'EMPTY' else ''))
        for c in tg:
            v = ' (older version, April 2025)' if c.version else ''
            anc = f'mt-l{c.l}' + ('-old' if c.version else '')
            out.append(details_cell(cur, c, anc, f'l = {c.l}{v}', f'target codimension {esc(c.h.get("codimension", ""))} · up to degree {c.degree}', pre(c.a[0][1] if c.a else '')) + '\n')
        out.append('\n')
    sr = cells(eid, 'source_ssm')
    if sr:
        out.append('## Source SSM (R-)polynomials {#source}\n\n')
        for c in sr:
            out.append(details_cell(cur, c, f'ms-l{c.l}', f'l = {c.l}', f'source codimension {esc(c.h.get("codimension", ""))} · up to degree {c.degree}', pre(c.a[0][1] if c.a else '')) + '\n')
        out.append('\n')
    out.append(data_footer(cur, eid))
    return ''.join(out)

# ====================================================================== tables


def table_page(kind, l, title, intro, path, open_short=False):
    cur = path
    items = [(eid, c) for eid in CELLS for c in cells(eid, kind) if c.l == l and not c.version]
    items.sort(key=lambda x: (x[1].codim if x[1].codim is not None else 999, entity_key(x[0])))
    out = [front(title), f'# {title}\n\n', intro + '\n\n',
           f'<p class="tpp-meta">{len(items)} entries. Each entry links to the singularity\'s own page and to its data file.</p>\n\n']
    last = object()
    for eid, c in items:
        if c.codim != last:
            out.append(f'\n## Codimension {c.codim}\n\n')
            last = c.codim
        if kind in ('tp', 'ssm', 's0'):
            body = ''.join(f'<div class="tpp-lbl">{lab}</div>' + pre(c.get(suf)) for lab, suf in (('Monomial basis', '_monomial'), ('Schur basis', '_schur')) if c.get(suf))
        else:
            body = pre(c.a[0][1] if c.a else '')
        meta = f'up to degree {c.degree}' if c.degree else ''
        anchor = re.sub(r'[^A-Za-z0-9_-]', '_', eid)
        out.append(f'<details class="tpp-cell" id="{anchor}"><summary><span class="tpp-cell-title">{name_html(eid)}</span>'
                   f'<span class="tpp-meta">{meta}</span><a class="tpp-goto" href="{rel_url(cur, page_of(eid))}">page</a>{file_link(cur, c)}</summary>{note_html(c)}{body}</details>\n')
    PAGES[path] = ''.join(out)
    return len(items)


def ktp_table():
    path = 'tables/ktp.md'
    out = [front('K-theoretic Thom polynomials'), '# K-theoretic Thom polynomials\n\n',
           f'See [K-theoretic Thom polynomials]({rel_md(path, "background/k-theory.md")}) for which notion of K-theoretic class is used.\n\n']
    for l in (0, 1):
        out.append(f'## Relative dimension l = {l}\n\n<div class="tpp-tablewrap"><table class="tpp-plain"><thead><tr><th>Singularity</th><th>codim</th><th>Grothendieck expansion</th><th>file</th></tr></thead><tbody>')
        items = sorted(((eid, c) for eid in CELLS for c in cells(eid, 'ktp') if c.l == l), key=lambda x: (x[1].codim, entity_key(x[0])))
        for eid, c in items:
            out.append(f'<tr><td>{elink(path, eid)}</td><td>{c.codim}</td><td>{M(c.get("_tex") or "")}</td><td>{file_link(path, c, "txt")}</td></tr>')
        out.append('</tbody></table></div>\n\n')
    PAGES[path] = ''.join(out)


def series_section(path):
    out = []
    by_mu = defaultdict(list)
    for eid in CELLS:
        for c in cells(eid, 'series'):
            by_mu[CAT.get(eid, {}).get('mu')].append((eid, c))
    for mu in sorted(k for k in by_mu if k is not None):
        out.append(f'\n## $\\mu={mu}$\n\n')
        for eid, c in sorted(by_mu[mu], key=lambda x: entity_key(x[0])):
            status = '' if not c.empty else ' <span class="tpp-soon">to be added</span>'
            inner = series_block(path, c).replace('id="series-cell"', '')
            out.append(f'<details class="tpp-cell" id="{eid}"><summary><span class="tpp-cell-title">{name_html(eid)}</span>{status}'
                       f'<a class="tpp-goto" href="{rel_url(path, page_of(eid))}">page</a></summary>{inner}</details>\n')
    return ''.join(out)


def knowledge_page():
    path = 'tables/knowledge.md'
    cols = ([('tp', l, f'Tp<br>l={l}') for l in range(6)] + [('series', None, 'Thom<br>series')]
            + [('ssm', l, f'SSM<br>l={l}') for l in range(7)] + [('ktp', l, f'KTp<br>l={l}') for l in range(2)])
    mcols = [('s0', l, f'S₀<br>l={l}') for l in range(1, 8)] + [('target_ssm', l, f'Target<br>l={l}') for l in range(1, 6)] + [('source_ssm', 1, 'Source<br>l=1')]

    def mark(eid, kind, l, single=None):
        cs = [c for c in cells(eid, kind, singleton=single) if c.l == l]
        if not cs:
            return '<td class="tpp-no">·</td>'
        c = cs[0]
        if c.empty:
            return '<td class="tpp-soon" title="placeholder">p</td>'
        return f'<td class="tpp-yes" title="{"up to degree " + str(c.degree) if c.degree else "known"}">{c.degree if c.degree else "✓"}</td>'
    out = [front('State of knowledge'), '# State of knowledge\n\n',
           'Which data the portal holds for each singularity. ✓ = known; a number = computed up to that cohomological degree; '
           '· = nothing recorded; p = placeholder entry. Generated from the data files on every build.\n\n',
           '## Mono-singularities\n\n<div class="tpp-tablewrap"><table class="tpp-grid"><thead><tr><th>Singularity</th><th>μ</th>'
           + ''.join(f'<th>{h}</th>' for _, _, h in cols) + '</tr></thead><tbody>']
    for mid in CAT:
        out.append(f'<tr><td>{elink(path, mid)}</td><td>{CAT[mid].get("mu", "") if CAT[mid].get("mu") is not None else ""}</td>'
                   + ''.join(mark(mid, k, l) if k != 'series' else (lambda cs: '<td class="tpp-no">·</td>' if not cs else ('<td class="tpp-soon">p</td>' if cs[0].empty else '<td class="tpp-yes">✓</td>'))(cells(mid, 'series')) for k, l, _ in cols)
                   + '</tr>')
    out.append('</tbody></table></div>\n\n## Multi-singularities\n\nIncluding single points (as multi-singularities).\n\n'
               '<div class="tpp-tablewrap"><table class="tpp-grid"><thead><tr><th>Multi-singularity</th>' + ''.join(f'<th>{h}</th>' for _, _, h in mcols) + '</tr></thead><tbody>')
    for eid in MULTI_IDS + [m for m in CAT if cells(m, 'target_ssm', singleton=True) or cells(m, 'source_ssm', singleton=True)]:
        single = None if eid in MULTI else True
        out.append(f'<tr><td>{elink(path, eid)}</td>' + ''.join(mark(eid, k, l, single) for k, l, _ in mcols) + '</tr>')
    out.append('</tbody></table></div>\n')
    PAGES[path] = ''.join(out)

# ====================================================================== catalogs (markers in content pages)


def contact_catalog(cur):
    rows = []
    for mid, e in CAT.items():
        n = len(CELLS.get(mid, []))
        rows.append(f'<tr><td>{elink(cur, mid)}</td><td>{e.get("mu", "") if e.get("mu") is not None else ""}</td><td>{M(e["sigma"]) if e.get("sigma") else ""}</td>'
                    f'<td>{esc(e.get("ideal") or "")}</td><td>{M(e["codim"]) if e.get("codim") else ""}</td><td>{esc(e.get("l_range") or "")}</td>'
                    f'<td>{esc(e.get("d") or "")}</td><td>{n}</td><td>{"" if e.get("mather") else "outside the list"}</td></tr>')
    return ('<div class="tpp-tablewrap"><table class="tpp-plain"><thead><tr><th>Name</th><th>μ</th><th>Σ</th><th>Ideal</th><th>Codim</th>'
            '<th>Occurs for</th><th>d</th><th>Data files</th><th></th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>\n'
            '<p class="tpp-legend">The last rows are singularities that have data on the portal but are not in Mather\'s list of 55.</p>\n')


def multi_catalog(cur):
    rows = []
    for eid in MULTI_IDS:
        parts = multi_parts(eid)
        cods = sorted({(c.l, c.codim) for c in CELLS[eid] if c.l is not None and c.codim is not None and not c.version})
        cod = ', '.join(f'{cd} (l={l})' for l, cd in cods[:3])
        rows.append(f'<tr><td>{elink(cur, eid)}</td><td>{sum(k for k, _ in parts)}</td><td>{esc(cod)}</td><td>{len(CELLS[eid])}</td></tr>')
    return ('Every multi-singularity for which the portal holds data has its own page. Single points (A₀, A₁, …) are on the pages of the '
            'corresponding [contact singularities](' + rel_md(cur, 'singularities/contact/index.md') + ').\n\n'
            '<div class="tpp-tablewrap"><table class="tpp-plain"><thead><tr><th>Multi-singularity</th><th>Points</th><th>Codimension</th><th>Data files</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>\n')


def tb_page():
    path = 'singularities/thom-boardman.md'
    groups = defaultdict(list)
    for mid, e in CAT.items():
        tb = e.get('tb_class') or e.get('sigma')
        if tb:
            groups[tb].append(mid)
    out = [front('Thom–Boardman classes'), '# Thom–Boardman classes\n\n',
           'Thom–Boardman singularities $\\Sigma^I$ are indexed by integer sequences $I$. The portal has no Thom polynomials of Thom–Boardman '
           'classes yet; when they are added, each class gets its own page like the contact singularities. For now this page lists, for each class '
           'that occurs, the contact singularities belonging to it (as recorded on the old site).\n\n',
           '<div class="tpp-tablewrap"><table class="tpp-plain"><thead><tr><th>Class</th><th>Contact singularities</th></tr></thead><tbody>']
    for tb in sorted(groups, key=lambda t: (len(re.sub(r'\D', '', t)), t)):
        out.append(f'<tr><td>{M(tb)}</td><td>' + ', '.join(elink(path, m) for m in groups[tb]) + '</td></tr>')
    out.append('</tbody></table></div>\n<p class="tpp-legend">Classes written like Σ<sup>{1,1,0}</sup> come from the old Thom polynomial tables; '
               'those written like Σ<sup>11</sup> are the abbreviated symbols of Mather\'s list. Unifying the two notations is an open task.</p>\n')
    PAGES[path] = ''.join(out)


def old_url_table(cur):
    rows = []
    for slug, v in OLD_URLS.items():
        new = v.get('new')
        tgt = (f'<a href="{rel_url(cur, (new + "/index.md") if new and not new.startswith("background") and new in ("singularities/contact", "singularities/multi", "tables") else (new + ".md" if new else "index.md"))}">{esc(new or "home")}</a>'
               if new is not None else '<span class="tpp-no">dropped</span>')
        rows.append(f'<tr><td><a href="{OLD_SITE}{slug}/">{esc(slug)}</a></td><td>{esc(v.get("title", ""))}</td><td>{tgt}</td></tr>')
    return ('<div class="tpp-tablewrap"><table class="tpp-plain"><thead><tr><th>Old page</th><th>Title</th><th>Now</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>\n')


def downloads_list(cur):
    files_dir = os.path.join(ROOT, 'files')
    local = sorted(os.listdir(files_dir)) if os.path.isdir(files_dir) else []
    items = []
    for name in sorted(set(local) | set(ATTACH)):
        href = rel_url(cur, 'files/' + name) if name in local else ATTACH[name]
        where = '' if name in local else ' <span class="tpp-meta">(still on the old site)</span>'
        items.append(f'<li><a href="{attr(href)}">{esc(name)}</a>{where}</li>')
    return '<ul class="tpp-cols">' + ''.join(items) + '</ul>\n'

# ====================================================================== assemble


def main():
    if os.path.exists(DOCS):
        shutil.rmtree(DOCS)
    shutil.copytree(os.path.join(ROOT, 'content'), DOCS)
    shutil.copytree(os.path.join(ROOT, 'data'), os.path.join(DOCS, 'data'))
    if os.path.isdir(os.path.join(ROOT, 'files')):
        shutil.copytree(os.path.join(ROOT, 'files'), os.path.join(DOCS, 'files'))

    for mid in CAT:
        PAGES[mono_page(mid)] = mono_page_text(mid)
    for eid in MULTI_IDS:
        PAGES[multi_page(eid)] = multi_page_text(eid)

    n = {}
    for l in range(6):
        n[f'tp-l{l}'] = table_page('tp', l, f'Thom polynomials, l = {l}',
                                   f'Thom polynomials of contact singularities of relative dimension $l={l}$, grouped by codimension.', f'tables/tp-l{l}.md')
    for l in range(7):
        n[f'ssm-l{l}'] = table_page('ssm', l, f'SSM-Thom polynomials, l = {l}',
                                    f'SSM-Thom polynomials of contact singularities of relative dimension $l={l}$; $t$ records the cohomological degree.', f'tables/ssm-l{l}.md')
    for l in range(1, 6):
        n[f'target-ssm-l{l}'] = table_page('target_ssm', l, f'Target SSM multi-singularity polynomials, l = {l}',
                                           'Target SSM polynomials of multi-singularities (single points included), grouped by codimension in the target.', f'tables/target-ssm-l{l}.md')
    n['source-ssm-l1'] = table_page('source_ssm', 1, 'Source SSM multi-singularity polynomials, l = 1',
                                    'Source SSM residue (R-)polynomials of multi-singularities, grouped by codimension in the source.', 'tables/source-ssm-l1.md')
    ktp_table()
    knowledge_page()
    tb_page()

    # tables index
    ti = 'tables/index.md'
    PAGES[ti] = (front('Tables') + '# Tables\n\nCross-sections of the data: one page per kind of data and relative dimension. Every entry also appears on its '
                 f'singularity\'s own page. The [state of knowledge](knowledge.md) page shows at a glance what is known.\n\n'
                 '| Data | Pages |\n|---|---|\n'
                 '| Thom polynomials | ' + ' · '.join(f'[l={l}](tp-l{l}.md)' for l in range(6)) + ' |\n'
                 '| Thom series (all l) | [Thom series](thom-series.md) |\n'
                 '| SSM-Thom polynomials | ' + ' · '.join(f'[l={l}](ssm-l{l}.md)' for l in range(7)) + ' |\n'
                 '| K-theoretic Thom polynomials | [l=0, 1](ktp.md) |\n'
                 '| Target SSM, multi-singularities | ' + ' · '.join(f'[l={l}](target-ssm-l{l}.md)' for l in range(1, 6)) + ' |\n'
                 '| Source SSM, multi-singularities | [l=1](source-ssm-l1.md) |\n'
                 '| S₀ series (empty multi-singularity) | [on the ∅ page](../singularities/multi/empty.md#s0) |\n')

    # write generated pages
    for rel, text in PAGES.items():
        p = os.path.join(DOCS, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(fix_root(rel, text))

    # fill markers in content pages and fix @ROOT@ links
    markers = {
        '<!-- TPP:contact-catalog -->': contact_catalog,
        '<!-- TPP:multi-catalog -->': multi_catalog,
        '<!-- TPP:thom-series -->': series_section,
        '<!-- TPP:old-urls -->': old_url_table,
        '<!-- TPP:downloads -->': downloads_list,
    }
    for dp, _, fns in os.walk(DOCS):
        for fn in fns:
            if not fn.endswith('.md'):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, DOCS).replace(os.sep, '/')
            if rel in PAGES:
                continue
            s = open(p, encoding='utf-8').read()
            for mk, fun in markers.items():
                if mk in s:
                    s = s.replace(mk, fun(rel))
            s = fix_root(rel, s)
            with open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(s)

    # all data as one zip
    os.makedirs(os.path.join(DOCS, 'downloads'), exist_ok=True)
    zp = os.path.join(DOCS, 'downloads', 'tpp-data.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for dp, _, fns in os.walk(os.path.join(ROOT, 'data')):
            for fn in sorted(fns):
                full = os.path.join(dp, fn)
                z.write(full, os.path.join('tpp-data', os.path.relpath(full, os.path.join(ROOT, 'data'))))
    print(f'docs/ written: {len(PAGES)} generated pages ({len(CAT)} contact, {len(MULTI_IDS)} multi), '
          f'{sum(len(v) for v in CELLS.values())} data files; table entries: ' + ', '.join(f'{k}={v}' for k, v in n.items()))


if __name__ == '__main__':
    main()
