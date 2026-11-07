# Thom Polynomial Portal — sandbox

Draft of the new [Thom Polynomial Portal](https://tpp.web.unc.edu/), migrated from WordPress in November 2026.
Published (unlisted, not indexed) at **https://rimanyi.github.io/tpp-sandbox/**.

## Where things are

| Folder | What it holds | Edit it? |
|---|---|---|
| `data/catalog/contact.yaml` | the list of contact singularities with their invariants | yes |
| `data/catalog/multi.yaml`, `lac.txt`, `old-urls.yaml` | extra text for multi-singularities, LAC splittings, old URL map | yes |
| `data/contact/<NAME>/` | data files of a singularity, e.g. `data/contact/A2/tp_l2.txt` | yes |
| `data/multi/<NAME>/` | data files of a multi-singularity, e.g. `data/multi/2A0+A2/`, `data/multi/EMPTY/` | yes |
| `content/` | the hand-written pages (Markdown), styles and scripts | yes |
| `files/` | PDFs, pictures and other downloads (empty for now; they are still linked from the old site) | yes |
| `scripts/` | the program that turns the above into web pages | rarely |
| `migration/` | the one-time conversion from WordPress, and its report | no |
| `.github/workflows/` | tells GitHub to rebuild the site after every push | no |

## Data files

One file per singularity × kind of data × relative dimension. Lines starting with `#` describe the contents
(source, codimension, degree, where it came from); the rest is Maple input:

```
# title: Thom polynomial of A2, relative dimension l=2
# kind: tp
# l: 2
# codimension: 6
...
Tp_A2_l2_monomial := 2*c[1]*c[5] +c[2]*c[4] +c[3]^2 +4*c[6]:
Tp_A2_l2_schur := 8*s[[6]] +s[[3,3]] +2*s[[4,2]] +4*s[[5,1]]:
```

To add a polynomial, add a file in the same format; the singularity page, the tables and the state-of-knowledge page
pick it up automatically.

## Building the site on your own computer (optional)

```
pip install -r requirements.txt
python scripts/build_site.py
mkdocs serve
```
