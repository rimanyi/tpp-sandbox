---
title: Home
hide:
  - navigation
---

# Thom Polynomial Portal

!!! warning "Sandbox"
    This is a **draft** of the new Thom Polynomial Portal, built from the WordPress site at
    [tpp.web.unc.edu](https://tpp.web.unc.edu/) in November 2026. It is not announced or linked anywhere,
    and it is hidden from search engines. The current portal remains [tpp.web.unc.edu](https://tpp.web.unc.edu/).

The Thom polynomial of a singularity $\Sigma$ is a universal characteristic class which expresses the fundamental
cohomology class of the $\overline{\Sigma}$-singularity submanifold of a map, in terms of the Chern classes of its
source and target manifolds. This portal collects the known Thom polynomials, and related data.

<div class="grid cards" markdown>

-   **[Contact singularities](singularities/contact/index.md)**

    The 55 local algebras of Mather's nice dimensions, each with its own page listing everything known about it.
    Start with [A₂](singularities/contact/A2.md).

-   **[Multi-singularities](singularities/multi/index.md)**

    Multi-singularities with data, including the empty one [∅](singularities/multi/empty.md), home of the S₀ series.

-   **[Tables](tables/index.md)**

    Thom polynomials, Thom series, SSM-Thom polynomials and K-theoretic Thom polynomials, one page per relative dimension.
    See also the [state of knowledge](tables/knowledge.md).

-   **[Local algebras](local-algebras/hierarchy.md)**

    Hierarchy, symmetries, the Large Algebra Collider and the 7-dimensional algebras.

</div>

## How the portal is organised

Every singularity, and every multi-singularity, has its own page. That page shows what is known about it: the local
algebra and basic invariants, the Thom polynomials for each relative dimension $l$, the Thom series, the SSM-Thom
polynomials, the K-theoretic Thom polynomials, its role as a multi-singularity, and its relations to other singularities.

Every polynomial is stored once, in a small plain-text file that Maple can read directly (`read "tp_l2.txt":`).
The singularity pages and the tables are generated from these files, so they never disagree with each other.
All data can be [downloaded](downloads.md) at once.

The portal is maintained by [Richárd Rimányi](https://rimanyi.web.unc.edu/).
