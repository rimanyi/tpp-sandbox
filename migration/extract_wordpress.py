"""One-time migration: WordPress export (WXR) of tpp.web.unc.edu -> this repository.

Usage:  python migration/extract_wordpress.py <export.xml> <repo-root>

Writes
  data/catalog/contact.yaml        catalog of contact mono-singularities (editable)
  data/catalog/multi.yaml          descriptions of special multi-singularities (editable)
  data/contact/<ID>/*.txt          data files of mono-singularities
  data/multi/<ID>/*.txt            data files of multi-singularities (incl. EMPTY)
  content/...                      prose pages converted from WordPress (editable)
  migration/REPORT.md              what was extracted, and what needs attention

This script is kept for the record.  After the migration the files above are
the source of truth and are edited directly; the script is not run again.
"""
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from tpplib import write_datafile, max_tdeg, min_tdeg, maple_name  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

EXPORT, ROOT = sys.argv[1], sys.argv[2]
SITE = 'https://tpp.web.unc.edu/'
UPLOADS_RE = re.compile(r'https?://tpp\.web\.unc\.edu/wp-content/uploads/sites/17537/\d{4}/\d{2}/([^"\s<>]+)')
NS = {'content': 'http://purl.org/rss/1.0/modules/content/', 'wp': 'http://wordpress.org/export/1.2/'}
REPORT = []          # lines for migration/REPORT.md
WRITTEN = []         # data files written

# ====================================================================== load
root = ET.parse(EXPORT).getroot()
PAGES = {}
ATTACH = []
for it in root.findall('./channel/item'):
    ptype = it.find('wp:post_type', NS).text or ''
    if ptype == 'attachment':
        ATTACH.append(it.find('wp:attachment_url', NS).text)
    if ptype != 'page':
        continue
    slug = it.find('wp:post_name', NS).text or '(draft)'
    PAGES[slug] = {'title': it.find('title').text or '', 'content': it.find('content:encoded', NS).text or '',
                   'modified': (it.find('wp:post_modified', NS).text or '')[:10],
                   'status': it.find('wp:status', NS).text or ''}


def meta(slug):
    return f'{SITE}{slug}/ (page modified {PAGES[slug]["modified"]})'


TOGGLE_RE = re.compile(r'\[toggle\s+title="([^"]*)"\s*\](.*?)\[/toggle\]', re.S)


def toggles(slug):
    c = PAGES[slug]['content']
    for m in TOGGLE_RE.finditer(c):
        yield html.unescape(m.group(1)).strip(), m.group(2), m.start(), c


def heading_before(c, pos):
    best = ''
    for m in re.finditer(r'<h[2-5][^>]*>(.*?)</h[2-5]>|<strong>\s*(.*?)\s*</strong>', c, re.S):
        if m.start() < pos:
            best = (m.group(1) or m.group(2) or '').strip()
        else:
            break
    return best


def strip_tags(s):
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s)


def clean_expr(expr):
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in expr.replace('\r', '').split('\n')]
    return '\n'.join(ln for ln in lines if ln)


def kv_table(body):
    """Parse an old-style key/value table (one row per key); nested tables are kept whole."""
    d = OrderedDict()
    m = re.search(r'<table[^>]*>', body)
    if not m:
        return d
    inner = body[m.end():body.rfind('</table>')]
    nested = []

    def keep(mm):
        nested.append(mm.group(0))
        return f'@@NESTED{len(nested) - 1}@@'
    inner = re.sub(r'<table.*?</table>', keep, inner, flags=re.S)
    for row in re.findall(r'<tr>(.*?)</tr>', inner, flags=re.S):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
        if len(cells) >= 2:
            val = re.sub(r'@@NESTED(\d+)@@', lambda m: nested[int(m.group(1))], cells[1])
            d[strip_tags(cells[0]).strip()] = val.strip()
    return d


def latex_to_math(s):
    """[latex]..[/latex] -> \\( .. \\)   (inline math for MathJax)."""
    s = re.sub(r'\[latex size="2"\](.*?)\[/latex\]', lambda m: r'\(\displaystyle ' + m.group(1).strip() + r'\)', s, flags=re.S)
    s = re.sub(r'\[latex\](.*?)\[/latex\]', lambda m: r'\(' + m.group(1).strip() + r'\)', s, flags=re.S)
    return s

# ====================================================================== entity ids

def mono_id(title):
    t = html.unescape(title).strip()
    if t.startswith('\\cup'):
        return 'Sigma3-pencil'
    if t.startswith('('):
        return 'ideal_' + re.sub(r'[\^()]', '', t).replace(',', '_')
    t = t.split('=')[0].strip()
    return re.sub(r'[_{},\s]', '', t)


CATALOG = OrderedDict()   # id -> dict
ORDER = {}                # id -> sort key


def load_catalog():
    slug = 'singularities-in-mathers-nice-dimensions'
    c = PAGES[slug]['content']
    for idx, m in enumerate(TOGGLE_RE.finditer(c)):
        title = html.unescape(m.group(1)).strip()
        name = re.split(r'\s*=\s*', title)[0].strip()
        mid = mono_id(name)
        tb = None
        for lm in re.finditer(r'\[latex\]\s*(\\Sigma[^\[]*?)\s*\[/latex\]', c[:m.start()]):
            tb = lm.group(1)
        mu = None
        for hm in re.finditer(r'<h4>\[latex\]\\mu=(\d+)\[/latex\]</h4>', c[:m.start()]):
            mu = int(hm.group(1))
        head = title.split('—')[0]
        pres = [x.strip() for x in re.split(r'\s*=\s*', head)[1:]]
        codim = re.search(r'codim=(.*)$', title)
        lines = [x.strip() for x in strip_tags(m.group(2)).split('\n') if x.strip()]
        entry = OrderedDict()
        entry['id'] = mid
        entry['name'] = name
        entry['mu'] = mu
        entry['sigma'] = tb
        entry['ideal'] = pres[-1] if pres else None
        if len(pres) > 1:
            entry['ideal_alternatives'] = pres[:-1]
        entry['codim'] = codim.group(1).strip() if codim else None
        entry['l_range'] = lines[0] if lines else None
        rest = lines[1:]
        d = [x for x in rest if x.startswith('d=')]
        entry['d'] = d[0][2:] if d else None
        nm = [x for x in rest if x.startswith('Name:')]
        if nm:
            entry['suggested_name'] = nm[0][5:].strip()
        notes = [x for x in rest if not x.startswith('d=') and not x.startswith('Name:')]
        if notes:
            entry['notes'] = notes
        entry['mather'] = True
        CATALOG[mid] = entry
        ORDER[mid] = (0, idx)
    REPORT.append(f'- Catalog: {len(CATALOG)} algebras read from Mather\'s list (`{slug}`).')


load_catalog()


def ensure_entity(mid, title=None):
    if mid in CATALOG:
        return
    e = OrderedDict()
    e['id'] = mid
    e['name'] = html.unescape(title or mid)
    e['mather'] = False
    m = re.fullmatch(r'A(\d+)', mid)
    if m:
        e['mu'] = int(m.group(1))
        e['ideal'] = f'(x^{int(m.group(1)) + 1})'
    m = re.fullmatch(r'I(\d)(\d)', mid)
    if m:
        p, q = int(m.group(1)), int(m.group(2))
        e['mu'] = p + q - 1
        e['ideal'] = f'(x^{p}+y^{q},xy)'
    if mid.startswith('ideal_'):
        e['ideal'] = html.unescape(title)
    if mid == 'Sigma3-pencil':
        e['name'] = 'Σ³ pencil'
        e['tex'] = r'\textstyle\bigcup_{\lambda}(x^2-\lambda yz,\,y^2-\lambda xz,\,z^2-\lambda xy)'
        e['notes'] = ['A one-parameter family; the union is open in Σ³ (l=0).']
    if mid.startswith('ideal_'):
        e['tex'] = html.unescape(title)
    CATALOG[mid] = e
    ORDER[mid] = (1, len(ORDER))


def entity_key(mid):
    return ORDER.get(mid, (2, mid))


def multi_id(title):
    t = html.unescape(title).strip()
    if t in ('∅', '&empty;', 'Ø', '&#8709;'):
        return 'EMPTY'
    t = re.sub(r'[{}_]', '', t)
    cnt = OrderedDict()
    for p in re.split(r'[,+*]', t):
        p = p.strip()
        if not p:
            continue
        m = re.fullmatch(r'(\d*)\s*([A-Za-z]+\d*)(?:\^(\d+))?', p)
        if not m:
            raise ValueError(f'cannot parse multi-singularity component {p!r} in {title!r}')
        mult = int(m.group(1) or 1) * int(m.group(3) or 1)
        nm = m.group(2)
        ensure_entity(nm)
        cnt[nm] = cnt.get(nm, 0) + mult
    parts = sorted(cnt.items(), key=lambda kv: entity_key(kv[0]))
    if len(parts) == 1 and parts[0][1] == 1:
        return parts[0][0]                    # a single point: this is the mono-singularity itself
    return '+'.join((str(k) if k > 1 else '') + n for n, k in parts)


def is_multi(eid):
    return eid == 'EMPTY' or '+' in eid or re.match(r'\d', eid)

# ====================================================================== provenance from the old table pages
SOURCES = {}         # (id, kind, l) -> source text
TBCLASS = {}         # id -> TB class string
REMARKS = defaultdict(set)
OLD_TABLE_PAGES = {'tps-l0': ('tp', 0), 'tps-l1': ('tp', 1), 'ktps-l0': ('ktp', 0), 'ktps-l1': ('ktp', 1),
                   'ssm-tps-l0': ('ssm', 0), 'ssm-tps-l1': ('ssm', 1), 'ssm-tp-l2': ('ssm', 2),
                   'ssm-tps-l3': ('ssm', 3), 'ssm-tps-l4': ('ssm', 4)}
for slug, (kind, l) in OLD_TABLE_PAGES.items():
    for title, body, _, _ in toggles(slug):
        mid = mono_id(title)
        kv = kv_table(body)
        tb = strip_tags(kv.get('Thom-Boardman class', '')).strip()
        if tb:
            TBCLASS.setdefault(mid, tb)
        rem = strip_tags(kv.get('Remarks', '')).strip()
        if rem:
            src = re.search(r'Source:\s*(.*)', rem, flags=re.S)
            if src:
                SOURCES[(mid, kind, l)] = re.sub(r'\s+', ' ', latex_to_math(src.group(1))).strip()
            r0 = re.sub(r'\s+', ' ', rem.split('Source:')[0]).strip()
            if r0:
                REMARKS[mid].add(r0)
REPORT.append(f'- Sources harvested from the old table pages: {len(SOURCES)} (entity, kind, l) triples; '
              f'Thom–Boardman classes for {len(TBCLASS)} singularities.')

# ====================================================================== data extraction helpers
CELLS = defaultdict(dict)   # entity -> kind_l -> info (for the report)


def data_path(eid, fname):
    top = 'multi' if is_multi(eid) else 'contact'
    return os.path.join(ROOT, 'data', top, eid, fname)


def put(eid, fname, header, assigns, info):
    p = data_path(eid, fname)
    write_datafile(p, header, assigns)
    WRITTEN.append(os.path.relpath(p, ROOT))
    CELLS[eid][fname] = info


def split_li_blocks(body):
    parts = re.split(r'<li>(.*?)</li>', body, flags=re.S)
    out = []
    for i in range(1, len(parts), 2):
        out.append((strip_tags(parts[i]).strip().rstrip(':').strip(), clean_expr(strip_tags(parts[i + 1]))))
    if not out:
        out.append(('', clean_expr(strip_tags(body))))
    return out


def codim_of(head):
    m = re.search(r'(-?\d+)', head or '')
    return int(m.group(1)) if m else None


VAR_TP = 'c[i] = quotient Chern classes (see Conventions); s[[lambda]] = Schur polynomial in the c[i]'
VAR_SSM = 't = cohomological degree; c[i], s[[lambda]] as for Thom polynomials'
VAR_PUSH = 't = cohomological degree; s[[i1,i2,...]] = f_*(c_{i1} c_{i2} ...), sc[[i1,...]] = f_*(Schur(i1,...)) (pushforward notation, see Conventions)'

# ---------------------------------------------------------------------- Thom polynomials, l = 0..5
TP_PAGES = {0: 'thom-polynomials-relative-dimension-l0', 1: 'thom-polynomials-relative-dimension-1',
            2: 'thom-polynomials-relative-dimension-l2', 3: 'thom-polynomials-relative-dimension-l3',
            4: 'thom-polynomials-relative-dimension-l4', 5: 'thom-polynomials-relative-dimension-l5'}
for l, slug in TP_PAGES.items():
    for title, body, pos, c in toggles(slug):
        mid = mono_id(title)
        ensure_entity(mid, title)
        blocks = dict(split_li_blocks(body))
        mono = [v for k, v in blocks.items() if 'monomial' in k.lower()]
        schur = [v for k, v in blocks.items() if 'schur' in k.lower()]
        head = heading_before(c, pos)
        codim = codim_of(head)
        n = maple_name(mid)
        hdr = OrderedDict(title=f'Thom polynomial of {mid}, relative dimension l={l}', entity=mid, kind='tp', l=l,
                          codimension=codim, variables=VAR_TP,
                          source=SOURCES.get((mid, 'tp', l), 'not recorded on the old site (to be added)'),
                          convention='TPP 2025', note=('heading on the old page: ' + strip_tags(head)) if 'beyond' in head else None,
                          **{'retrieved-from': meta(slug)})
        assigns = []
        if mono:
            assigns.append((f'Tp_{n}_l{l}_monomial', mono[0], False))
        if schur:
            assigns.append((f'Tp_{n}_l{l}_schur', schur[0], False))
        put(mid, f'tp_l{l}.txt', hdr, assigns, {'codim': codim})

# ---------------------------------------------------------------------- SSM-Thom polynomials, l = 0..6
for l in range(7):
    slug = f'ssm-thom-polynomials-for-l{l}'
    for title, body, pos, c in toggles(slug):
        mid = mono_id(title)
        ensure_entity(mid, title)
        blocks = dict(split_li_blocks(body))
        mono = [v for k, v in blocks.items() if 'monomial' in k.lower()]
        schur = [v for k, v in blocks.items() if 'schur' in k.lower()]
        codim = codim_of(heading_before(c, pos))
        n = maple_name(mid)
        deg = max_tdeg(mono[0]) if mono else None
        hdr = OrderedDict(title=f'SSM-Thom polynomial of {mid}, relative dimension l={l}', entity=mid, kind='ssm', l=l,
                          codimension=f'{codim}   (the lowest-degree part is the Thom polynomial)',
                          **{'computed-up-to-degree': deg}, variables=VAR_SSM,
                          source=SOURCES.get((mid, 'ssm', l), 'not recorded on the old site (to be added)'),
                          convention='TPP 2025', **{'retrieved-from': meta(slug)})
        assigns = []
        if mono:
            assigns.append((f'SSM_{n}_l{l}_monomial', mono[0], False))
        if schur:
            assigns.append((f'SSM_{n}_l{l}_schur', schur[0], False))
        put(mid, f'ssm_l{l}.txt', hdr, assigns, {'codim': codim, 'degree': deg})

# ---------------------------------------------------------------------- K-theoretic Thom polynomials, l = 0,1
for l, slug in [(0, 'ktps-l0'), (1, 'ktps-l1')]:
    for title, body, pos, c in toggles(slug):
        mid = mono_id(title)
        ensure_entity(mid, title)
        kv = kv_table(body)
        expr = re.sub(r'\s+', ' ', strip_tags(kv.get('K-Thom polynomial in Grothendieck expansion', ''))).strip()
        codim = codim_of(heading_before(c, pos))
        hdr = OrderedDict(title=f'K-theoretic Thom polynomial of {mid}, relative dimension l={l}', entity=mid, kind='ktp', l=l,
                          codimension=codim,
                          format='TeX-like Grothendieck expansion g_{lambda}, stored as a Maple string (to be normalised to Maple syntax)',
                          variables='g_{lambda} = (stable) Grothendieck polynomial; K-theoretic fundamental class = class of the structure sheaf of a resolution, pushed forward',
                          source=SOURCES.get((mid, 'ktp', l), 'not recorded on the old site (to be added)'),
                          **{'retrieved-from': meta(slug)})
        put(mid, f'ktp_l{l}.txt', hdr, [(f'KTp_{maple_name(mid)}_l{l}_tex', expr, True)], {'codim': codim})

# ---------------------------------------------------------------------- Thom series (all l)
SERIES_SLUG = 'tp-linfinity'
for title, body, pos, c in toggles(SERIES_SLUG):
    mid = mono_id(title)
    ensure_entity(mid, title)
    kv = kv_table(body)
    n = maple_name(mid)
    hdr = OrderedDict(title=f'Thom series of {mid} (all relative dimensions at once)', entity=mid, kind='series')
    hdr['local-algebra'] = strip_tags(kv.get('Local algebra', '')).strip()
    hdr['tp-degree'] = strip_tags(kv.get('Tp degree', '')).strip()
    assigns = []
    notes = []
    rp = kv.get('Residue presentations')
    i = 0
    if rp:
        for row in re.findall(r'<tr>(.*?)</tr>', rp, flags=re.S):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
            if len(cells) < 2:
                continue
            i += 1
            prof = re.search(r'\[latex\](.*?)\[/latex\]', cells[0], flags=re.S)
            hdr[f'profile-{i}'] = prof.group(1).strip() if prof else strip_tags(cells[0]).strip()
            cell = cells[1]
            boxes = re.findall(r'<strong>(.*?)</strong>\s*<textarea[^>]*>(.*?)</textarea>', cell, flags=re.S)
            disp = re.sub(r'<div[^>]*>\s*<strong>.*?</strong>\s*<textarea.*?</textarea>\s*</div>', '', cell, flags=re.S)
            disp = re.sub(r'\s+', ' ', strip_tags(latex_to_math(disp))).strip()
            assigns.append((f'Ts_{n}_profile{i}_display', disp, True))
            for j, (lab, expr) in enumerate(boxes, 1):
                lab = strip_tags(lab).strip().rstrip(':')
                hdr[f'box-{i}-{j}'] = lab
                assigns.append((f'F_{n}_profile{i}' + (f'_{j}' if len(boxes) > 1 else ''), html.unescape(expr).strip(), False))
    for k, v in kv.items():
        if k in ('Local algebra', 'Tp degree', 'Residue presentations', 'Explicit Thom series') or 'mu' in k:
            continue
        notes.append(f'{strip_tags(latex_to_math(k)).strip()}: {strip_tags(latex_to_math(v)).strip()}')
    ex = kv.get('Explicit Thom series', '')
    exm = re.search(r'\[latex\](.*?)\[/latex\]', ex, flags=re.S)
    if exm:
        assigns.append((f'Ts_{n}_explicit_tex', exm.group(1).strip(), True))
    elif ex:
        notes.append('Explicit Thom series: ' + strip_tags(latex_to_math(ex)).strip())
    if notes:
        hdr['note'] = '\n'.join(notes)
    hdr['convention'] = 'TPP 2026 (signs and orientations may differ from pre-2026 versions of the Thom series page)'
    hdr['source'] = 'not recorded on the old site (to be added)'
    hdr['retrieved-from'] = meta(SERIES_SLUG)
    put(mid, 'series.txt', hdr, assigns, {'profiles': i, 'explicit': bool(exm)})

# ---------------------------------------------------------------------- multi-singularities
TERM_RE = re.compile(r'([+-]?)\s*(\d+(?:/\d+)?)?\s*\*?\s*(s\[\[[\d,]*\]\](?:\^\d+)?(?:\*s\[\[[\d,]*\]\](?:\^\d+)?)*)')


def parse_tseries(expr):
    expr = re.sub(r's\[(?!\[)([\d,]*)\]', r's[[\1]]', expr)
    flat = re.sub(r'\s+', ' ', expr) + ' '
    out = {}
    for m in re.finditer(r't\s*\^\s*(\d+)\s*\*\s*\((.*?)\)\s*(?=\+\s*t|$)', flat, re.S):
        d = {}
        for tm in TERM_RE.finditer(m.group(2)):
            co = Fraction(tm.group(2)) if tm.group(2) else Fraction(1)
            if tm.group(1) == '-':
                co = -co
            d[tm.group(3)] = d.get(tm.group(3), 0) + co
        out[int(m.group(1))] = {k: v for k, v in d.items() if v}
    return out


TARGET = {}   # l -> {eid: (expr, codim)}
for l in range(1, 6):
    slug = f'target-ssm-multi-singularity-thom-polynomials-for-l{l}'
    TARGET[l] = {}
    for title, body, pos, c in toggles(slug):
        eid = multi_id(title)
        blocks = split_li_blocks(body)
        expr = blocks[0][1]
        codim = codim_of(heading_before(c, pos))
        deg = max_tdeg(expr)
        TARGET[l][eid] = expr
        fname = f'target_ssm_l{l}.txt' if is_multi(eid) else f'multi_target_ssm_l{l}.txt'
        hdr = OrderedDict(title=f'Target SSM multi-singularity Thom polynomial of {eid}, relative dimension l={l}',
                          entity=eid, kind='target_ssm', l=l, codimension=f'{codim} (in the target)',
                          **{'computed-up-to-degree': deg}, variables=VAR_PUSH,
                          source='not recorded on the old site (to be added)', **{'retrieved-from': meta(slug)})
        put(eid, fname, hdr, [(f'TargetSSM_{maple_name(eid)}_l{l}', expr, False)], {'codim': codim, 'degree': deg})

# older target S-polynomial page (441-2), l = 1
OLD_TGT = '441-2'
cmp_agree, cmp_disagree, cmp_only_old = 0, [], []
for title, body, pos, c in toggles(OLD_TGT):
    eid = multi_id(title)
    expr = clean_expr(strip_tags(body))
    expr_norm = re.sub(r's\[(?!\[)([\d,]*)\]', r's[[\1]]', expr)
    head = strip_tags(heading_before(c, pos))
    deg = max_tdeg(expr)
    note = None
    if eid in TARGET[1]:
        a, b = parse_tseries(TARGET[1][eid]), parse_tseries(expr)
        common = sorted(set(a) & set(b))
        bad = [d for d in common if a[d] != b[d]]
        if not common:
            cmp_disagree.append((eid, 'no common degrees parsed'))
            note = f'could not be compared automatically with the 2025-06 target SSM page (degrees {min(b or [0])}..{max(b or [0])} vs {min(a or [0])}..{max(a or [0])}).'
        elif bad:
            cmp_disagree.append((eid, bad))
            note = (f'DISAGREES with target_ssm (2025-06 page) in degrees {bad}; agrees in degrees '
                    f'{[d for d in common if d not in bad]}. To be checked.')
        else:
            cmp_agree += 1
            note = (f'agrees term by term with the 2025-06 target SSM page in all common degrees '
                    f'{min(common)}..{max(common)}; this older version extends to degree {deg}.')
    else:
        cmp_only_old.append(eid)
        note = 'only recorded on this older page.'
    base = 'target_ssm_l1' if is_multi(eid) else 'multi_target_ssm_l1'
    fname = base + ('.txt' if eid not in TARGET[1] else '.v2025-04.txt')
    hdr = OrderedDict(title=f'Target SSM residue (S-)polynomial of {eid}, l=1 (version of April 2025)',
                      entity=eid, kind='target_ssm', l=1, codimension=head.replace('codimension=', '').strip() + ' (in the target)',
                      **{'computed-up-to-degree': deg}, variables=VAR_PUSH + '\n(this older page wrote s[i,j] for s[[i,j]]; normalised here)',
                      note=note, source='not recorded on the old site (to be added)', **{'retrieved-from': meta(OLD_TGT)})
    put(eid, fname, hdr, [(f'TargetSSM_{maple_name(eid)}_l1' + ('' if eid not in TARGET[1] else '_v2025_04'), expr_norm, False)],
        {'degree': deg, 'version': '2025-04'})
REPORT.append(f'- Old target page `441-2` (April 2025) compared with `target-ssm-...-for-l1` (June 2025): '
              f'{cmp_agree} multi-singularities agree in all common degrees; disagreements: '
              + (', '.join(f'{e} in degrees {d}' for e, d in cmp_disagree) or 'none')
              + f'; only on the old page: {", ".join(cmp_only_old) or "none"}. Both versions are kept as separate files.')

# source SSM (R-)polynomials, l = 1
SRC = 'source-ssm-multi-singularity-l1'
for title, body, pos, c in toggles(SRC):
    eid = multi_id(title)
    expr = clean_expr(strip_tags(body))
    head = strip_tags(heading_before(c, pos))
    deg = max_tdeg(expr)
    fname = 'source_ssm_l1.txt' if is_multi(eid) else 'multi_source_ssm_l1.txt'
    hdr = OrderedDict(title=f'Source SSM residue (R-)polynomial of {eid}, l=1', entity=eid, kind='source_ssm', l=1,
                      codimension=head.replace('codimension=', '').strip() + ' (in the source)',
                      **{'computed-up-to-degree': deg}, variables='t = cohomological degree; c[i] = quotient Chern classes',
                      source='not recorded on the old site (to be added)', **{'retrieved-from': meta(SRC)})
    put(eid, fname, hdr, [(f'SourceSSM_{maple_name(eid)}_l1', expr, False)], {'degree': deg})

# S0 series of the empty multi-singularity
S0 = 's0-series'
c = PAGES[S0]['content']
for m in TOGGLE_RE.finditer(c):
    l = int(re.search(r'l=(\d+)', heading_before(c, m.start())).group(1))
    basis = 'monomial' if 'monomial' in m.group(1) else 'schur'
    expr = clean_expr(strip_tags(m.group(2)))
    CELLS.setdefault('_s0', {}).setdefault(l, {})[basis] = expr
for l, d in sorted(CELLS.pop('_s0').items()):
    deg = max_tdeg(d['monomial'])
    hdr = OrderedDict(title=f'S0 series of the empty multi-singularity, relative dimension l={l}',
                      entity='EMPTY', kind='s0', l=l, **{'computed-up-to-degree': deg},
                      variables=VAR_PUSH, note='S0(l) = log MS(l), where MS(l) = target SSM polynomial of the empty multi-singularity (master series)',
                      source='not recorded on the old site (to be added)', **{'retrieved-from': meta(S0)})
    put('EMPTY', f's0_l{l}.txt', hdr, [(f'S0_l{l}_monomial', d['monomial'], False), (f'S0_l{l}_schur', d['schur'], False)], {'degree': deg})

# ====================================================================== catalog enrichment and output
SYM = {}
for m in re.finditer(r'^\s*\[([A-Za-z0-9_]+),(.*)$', strip_tags(PAGES['symmetry-of-mather-singularities']['content']), re.M):
    SYM[mono_id(m.group(1))] = ('[' + m.group(1) + ',' + m.group(2)).strip().rstrip(',').strip()

LAC = [ln.strip() for ln in strip_tags(PAGES['large-algebra-collider-lac']['content']).split('\n') if '->' in ln]

for mid, e in CATALOG.items():
    if mid in TBCLASS:
        e['tb_class'] = TBCLASS[mid]
    if REMARKS.get(mid):
        e['remarks'] = sorted(REMARKS[mid])
    if mid in SYM:
        e['symmetry_record'] = SYM[mid]

os.makedirs(os.path.join(ROOT, 'data', 'catalog'), exist_ok=True)


def dump_yaml(obj, path, header):
    def conv(o):
        if isinstance(o, OrderedDict) or isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(x) for x in o]
        return o
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(header)
        yaml.safe_dump(conv(obj), f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=False)


dump_yaml(list(CATALOG.values()), os.path.join(ROOT, 'data', 'catalog', 'contact.yaml'),
          '# Catalog of contact mono-singularities (local algebras).\n'
          '# One entry per singularity; the site builds a page for each entry.\n'
          '# Fields: id (used in URLs and data folder names), name, mu, sigma (Thom-Boardman symbol as in Mather\'s list),\n'
          '#   tb_class (Thom-Boardman class, from the old Tp tables), ideal, codim (as a function of l), l_range,\n'
          '#   d (d_i = dim m^i/m^{i+1}), notes, remarks, symmetry_record, mather (true = in Mather\'s list of 55).\n'
          '# Migrated from tpp.web.unc.edu on 2026-11-07; edit freely.\n\n')

MULTI_CAT = [OrderedDict(id='EMPTY', name='∅', description=(
    'The multi-singularity with no points. Its target SSM polynomial is the master series MS(l), and the S0 series is '
    'its logarithm, S0(l) = log MS(l). Only for the empty multi-singularity is the logarithm the natural object.'),
    s0_intro=clean_expr(strip_tags(PAGES[S0]['content'][:PAGES[S0]['content'].find('<h4>')])))]
dump_yaml(MULTI_CAT, os.path.join(ROOT, 'data', 'catalog', 'multi.yaml'),
          '# Descriptions of multi-singularities that need more than their name.\n'
          '# Every multi-singularity with a data folder under data/multi/ gets a page; entries here add text to it.\n\n')

with open(os.path.join(ROOT, 'data', 'catalog', 'lac.txt'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# Large Algebra Collider: elementary splittings of algebras (one rule per line).\n'
            '# Migrated from tpp.web.unc.edu/large-algebra-collider-lac/ ; entity pages read their splittings from here.\n')
    f.write('\n'.join(LAC) + '\n')

# ====================================================================== prose pages
PAGE_MAP = OrderedDict([   # old slug -> new path (site-relative, without trailing slash) ; None = not converted
    ('home', ''),
    ('ordinary-thom-polynomials', 'background/thom-polynomials'),
    ('ssm-thom-polynomials', 'background/ssm'),
    ('ktps', 'background/k-theory'),
    ('mather-singularities', 'singularities/contact'),
    ('singularities-in-mathers-nice-dimensions', 'singularities/contact'),
    ('multi-singularity-loci', 'singularities/multi'),
    ('list-of-multi-singularities-in-the-mather-range', 'singularities/multi/mather-range'),
    ('list-of-multi-singularities-l1', 'singularities/multi/list-l1'),
    ('hierarchy-of-contact-singularities', 'local-algebras/hierarchy'),
    ('symmetry-of-mather-singularities', 'local-algebras/symmetries'),
    ('large-algebra-collider-lac', 'local-algebras/lac'),
    ('7-dimensional-algebras', 'local-algebras/7-dimensional'),
    ('tp-linfinity', 'tables/thom-series'),
    ('ts-new', 'tables/thom-series'),
    ('thom-polynomials-relative-dimension-l0', 'tables/tp-l0'), ('thom-polynomials-relative-dimension-1', 'tables/tp-l1'),
    ('thom-polynomials-relative-dimension-l2', 'tables/tp-l2'), ('thom-polynomials-relative-dimension-l3', 'tables/tp-l3'),
    ('thom-polynomials-relative-dimension-l4', 'tables/tp-l4'), ('thom-polynomials-relative-dimension-l5', 'tables/tp-l5'),
    ('tps-l0', 'tables/tp-l0'), ('tps-l1', 'tables/tp-l1'),
    *[(f'ssm-thom-polynomials-for-l{l}', f'tables/ssm-l{l}') for l in range(7)],
    ('ssm-tps-l0', 'tables/ssm-l0'), ('ssm-tps-l1', 'tables/ssm-l1'), ('ssm-tp-l2', 'tables/ssm-l2'),
    ('ssm-tps-l3', 'tables/ssm-l3'), ('ssm-tps-l4', 'tables/ssm-l4'),
    ('ktps-l0', 'tables/ktp'), ('ktps-l1', 'tables/ktp'),
    ('s0-series', 'singularities/multi/empty'),
    *[(f'target-ssm-multi-singularity-thom-polynomials-for-l{l}', f'tables/target-ssm-l{l}') for l in range(1, 6)],
    ('441-2', 'tables/target-ssm-l1'),
    ('source-ssm-multi-singularity-l1', 'tables/source-ssm-l1'),
    ('image-milnor-numbers', 'derived/image-milnor-numbers'),
    ('image-milnor-functions', 'derived/image-milnor-numbers'),
    ('rrs-codes', 'downloads'),
    ('future', 'about'),
    ('thom-polynomial-wiki-page-test', None),
])

BLOCK = r'(?:table|tbody|thead|tr|td|th|ul|ol|li|h[1-6]|hr|div|p|details|summary|blockquote|pre)'


def rewrite_links(s):
    def up(m):
        return '@ROOT@/files/' + m.group(1)
    s = UPLOADS_RE.sub(up, s)

    def pg(m):
        slug = m.group(1)
        if slug in PAGE_MAP and PAGE_MAP[slug] is not None:
            return '@ROOT@/' + PAGE_MAP[slug] + ('/' if PAGE_MAP[slug] else '')
        return m.group(0)
    s = re.sub(r'https?://tpp\.web\.unc\.edu/([a-z0-9-]+)/?(?=")', pg, s)
    s = re.sub(r'https?://tpp\.web\.unc\.edu/?(?=")', '@ROOT@/', s)
    return s


def wp_to_html(s):
    """Convert WordPress page content to clean HTML (math as \\( \\), toggles as <details>)."""
    s = s.replace('\r', '')
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'\[toggles[^\]]*\]', '', s)
    s = s.replace('[/toggles]', '')
    s = re.sub(r'\[toggle\s+title="([^"]*)"\s*\]', lambda m: '<details class="wp-toggle"><summary>' + latex_to_math(m.group(1)) + '</summary><div class="wp-toggle-body">', s)
    s = s.replace('[/toggle]', '</div></details>')
    s = latex_to_math(s)
    s = re.sub(r'\s(?:style|width|height|button_color|text_color)="[^"]*"', '', s)
    s = re.sub(r'<(/?)HR\b', r'<\1hr', s)
    s = re.sub(r'<(/?)A\b', r'<\1a', s)
    s = re.sub(r'</A>', '</a>', s)
    # whitespace (with a newline) next to block-level tags carries no meaning (like wpautop)
    s = re.sub(r'[ \t]*\n\s*(?=</?' + BLOCK + r'\b)', '', s)
    s = re.sub(r'(<' + BLOCK + r'\b[^>]*>|</' + BLOCK + r'>)[ \t]*\n\s*', r'\1', s)
    s = re.sub(r'<textarea[^>]*>(.*?)</textarea>', lambda m: '<pre class="maple" data-search-exclude>' + m.group(1).strip() + '</pre>', s, flags=re.S)
    s = re.sub(r'\n{3,}', '\n\n', s).strip()
    s = rewrite_links(s)
    return s


def html_block(s):
    return '<div class="wp-content" markdown="0">\n' + s + '\n</div>\n'


def heading_md(text, level):
    t = text
    t = re.sub(r'\[latex[^\]]*\](.*?)\[/latex\]', lambda m: '$' + m.group(1).strip() + '$', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t).strip()
    return '#' * level + ' ' + t


def convert_page(slug, title, intro_md='', cut_at=None, extra_md=''):
    """Convert a WordPress page to Markdown: top-level headings become Markdown headings (for the
    table of contents), everything else becomes raw HTML blocks."""
    c = PAGES[slug]['content']
    if cut_at is not None:
        c = c[:cut_at]
    # top-level headings
    tokens = list(re.finditer(r'\[toggle\b|\[/toggle\]|<table\b|</table>|<h([2-5])[^>]*>(.*?)</h\1>', c, re.S))
    depth = 0
    heads = []
    for t in tokens:
        g = t.group(0)
        if g.startswith('[toggle') or g.startswith('<table'):
            depth += 1
        elif g.startswith('[/toggle') or g.startswith('</table'):
            depth -= 1
        elif depth == 0:
            heads.append((t.start(), t.end(), int(t.group(1)), t.group(2)))
    levels = sorted(set(h[2] for h in heads))
    lmap = {lv: min(2 + i, 4) for i, lv in enumerate(levels)}
    out = [f'# {title}\n', intro_md]
    pos = 0
    for st, en, lv, text in heads:
        seg = wp_to_html(c[pos:st])
        if seg:
            out.append(html_block(seg))
        out.append(heading_md(text, lmap[lv]) + '\n')
        pos = en
    seg = wp_to_html(c[pos:])
    if seg:
        out.append(html_block(seg))
    out.append(extra_md)
    return '\n'.join(x for x in out if x is not None)


def write_content(rel, text, front=None):
    p = os.path.join(ROOT, 'content', rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fm = ''
    if front:
        fm = '---\n' + ''.join(f'{k}: {v}\n' for k, v in front.items()) + '---\n\n'
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(fm + text.rstrip() + '\n')


SRC_NOTE = lambda slug: (f'\n<p class="migrated">Migrated from the WordPress page '
                         f'<a href="{SITE}{slug}/">{slug}</a> (last modified {PAGES[slug]["modified"]}).</p>\n')

write_content('background/thom-polynomials.md',
              convert_page('ordinary-thom-polynomials', 'What is a Thom polynomial') + SRC_NOTE('ordinary-thom-polynomials'))
write_content('background/ssm.md', convert_page('ssm-thom-polynomials', 'SSM-Thom polynomials',
              intro_md='!!! note "To be written"\n    The old site said "explanation to be added later". The tables are under [Tables](@MD@/tables/index.md).\n')
              + SRC_NOTE('ssm-thom-polynomials'))
write_content('background/k-theory.md', convert_page('ktps', 'K-theoretic Thom polynomials') + SRC_NOTE('ktps'))

# Mather's list: introduction + generated catalog table
mc = PAGES['singularities-in-mathers-nice-dimensions']['content']
first_mu = mc.find('<h4>[latex]\\mu=0')
write_content('singularities/contact/index.md',
              convert_page('singularities-in-mathers-nice-dimensions', 'Contact singularities', cut_at=first_mu)
              + '\n## The list\n\n<!-- TPP:contact-catalog -->\n'
              + SRC_NOTE('singularities-in-mathers-nice-dimensions'))
write_content('singularities/multi/index.md',
              '# Multi-singularities\n\n<!-- TPP:multi-catalog -->\n\n## Lists of multi-singularities\n\n'
              '- [Multi-singularities in the Mather range, l = 1…5](mather-range.md)\n'
              '- [Multi-singularities for l = 1, up to codimension 14](list-l1.md)\n\n'
              '## Picture from the old site\n\n' + html_block(wp_to_html(PAGES['multi-singularity-loci']['content']))
              + SRC_NOTE('multi-singularity-loci'))
write_content('singularities/multi/mather-range.md', convert_page('list-of-multi-singularities-in-the-mather-range', 'Multi-singularities in the Mather range')
              + SRC_NOTE('list-of-multi-singularities-in-the-mather-range'), front={'search': '\n  exclude: true'})
write_content('singularities/multi/list-l1.md', convert_page('list-of-multi-singularities-l1', 'Multi-singularities for l = 1')
              + SRC_NOTE('list-of-multi-singularities-l1'), front={'search': '\n  exclude: true'})
write_content('local-algebras/hierarchy.md', convert_page('hierarchy-of-contact-singularities', 'Hierarchy and symmetries')
              + SRC_NOTE('hierarchy-of-contact-singularities'))
write_content('local-algebras/symmetries.md', convert_page('symmetry-of-mather-singularities', 'Symmetries of Mather singularities')
              + SRC_NOTE('symmetry-of-mather-singularities'))
write_content('local-algebras/lac.md', convert_page('large-algebra-collider-lac', 'Large Algebra Collider (LAC)')
              + SRC_NOTE('large-algebra-collider-lac'))
write_content('local-algebras/7-dimensional.md', convert_page('7-dimensional-algebras', '7-dimensional algebras')
              + SRC_NOTE('7-dimensional-algebras'))
sc = PAGES['tp-linfinity']['content']
write_content('tables/thom-series.md',
              convert_page('tp-linfinity', 'Thom series', cut_at=sc.find('<h4>[latex]\\mu=1'))
              + '\n<!-- TPP:thom-series -->\n' + SRC_NOTE('tp-linfinity'))
write_content('derived/image-milnor-numbers.md',
              convert_page('image-milnor-numbers', 'Image Milnor numbers',
                           intro_md='!!! info "Where this comes from"\n    Image Milnor numbers are consequences of the '
                                    '[S₀ series](@MD@/singularities/multi/empty.md) of the empty multi-singularity.\n')
              + SRC_NOTE('image-milnor-numbers'), front={'search': '\n  exclude: true'})

# downloads (RR's codes) and about (future plans) get converted fragments
DL_CODES = convert_page('rrs-codes', "RR's codes")[len("# RR's codes\n"):]
FUTURE = convert_page('future', 'Future')[len('# Future\n'):]
with open(os.path.join(ROOT, 'migration', 'fragments.json'), 'w', encoding='utf-8') as f:
    json.dump({'rrs_codes': DL_CODES, 'future': FUTURE, 'home_old': wp_to_html(PAGES['home']['content'])}, f, ensure_ascii=False, indent=1)

# old URL map for the About page
with open(os.path.join(ROOT, 'data', 'catalog', 'old-urls.yaml'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# Where each page of the old WordPress site went (old slug -> new path). null = dropped.\n')
    for slug, new in PAGE_MAP.items():
        t = PAGES.get(slug, {}).get('title', '')
        f.write(f'{slug}: {{new: {json.dumps(new)}, title: {json.dumps(html.unescape(t))}}}\n')

# attachments list
with open(os.path.join(ROOT, 'migration', 'attachments.txt'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(ATTACH) + '\n')

# ====================================================================== report
mono = sorted({e for e in CELLS if not is_multi(e)}, key=entity_key)
multi = sorted({e for e in CELLS if is_multi(e)})
REPORT.insert(0, f'- Data files written: {len(WRITTEN)}, for {len(mono)} mono-singularities and {len(multi)} multi-singularities (including ∅).')
REPORT.append(f'- Singularities with data that are not in Mather\'s list (added to the catalog with mather: false): '
              + ', '.join(e for e in CATALOG if not CATALOG[e]['mather']))
REPORT.append(f'- Mather algebras without any data file: '
              + ', '.join(e for e in CATALOG if CATALOG[e]['mather'] and e not in CELLS))
with open(os.path.join(ROOT, 'migration', 'REPORT.md'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('# Migration report\n\nGenerated by `migration/extract_wordpress.py` from the WordPress export of 2026-10-18.\n\n'
            + '\n'.join(REPORT) + '\n')
print('\n'.join(REPORT))
