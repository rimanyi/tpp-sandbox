---
title: Conventions and notation
---

# Conventions and notation

!!! note "Draft"
    This page collects the notation used on the old site in one place. It was assembled during the migration and
    still needs to be checked and completed.

## Thom polynomials

For a contact singularity $\Sigma_Q$ of relative dimension $l$ (map germs $(\mathbb{C}^n,0)\to(\mathbb{C}^{n+l},0)$),
the Thom polynomial depends only on the *quotient Chern classes* $c_i$, defined by

$$\frac{1+b_1t+b_2t^2+\dots}{1+a_1t+a_2t^2+\dots}=1+c_1t+c_2t^2+\dots,$$

where $a_i$ and $b_i$ are the Chern classes of the source and the target. For a partition
$\lambda=(\lambda_1,\dots,\lambda_r)$ the Schur polynomial is $s_\lambda=\det(c_{\lambda_i+j-i})_{i,j=1,\dots,r}$.
See [What is a Thom polynomial](thom-polynomials.md) for the definitions.

In the data files (Maple syntax): `c[i]` is $c_i$, and `s[[3,1]]` is $s_{(3,1)}$.

## SSM-Thom polynomials

An SSM-Thom polynomial is written as a series in an auxiliary variable `t` that records the cohomological degree:
`+t^4*( ... ) +t^5*( ... ) + ...`. The lowest-degree part (degree = codimension) is the ordinary Thom polynomial.
Each series is known only up to a certain degree, recorded in the data file as `computed-up-to-degree`.

## Multi-singularities: pushforward notation

On the multi-singularity pages, `s[[i1,i2,...]]` denotes the pushforward $f_*(c_{i_1}c_{i_2}\cdots)$ and
`sc[[i1,i2,...]]` denotes $f_*(\mathrm{Schur}(i_1,i_2,\dots))$. The older target page (April 2025) wrote `s[i,j]`
for `s[[i,j]]`; the data files use the double brackets throughout.

The target codimension on the older page was written as "$k(+1)$". *To be explained.*

Multi-singularities are named by their points with multiplicities, for example $2\mathrm{A}_0+\mathrm{A}_2$; the
points are ordered as in Mather's list. In file and page names this is written `2A0+A2`, and the empty
multi-singularity is `EMPTY` (page: `empty`). *This naming is provisional.*

## Thom series

See the introduction of the [Thom series](../tables/thom-series.md) page: residue presentations $F_{Q,\omega}$ for a
filtration profile $\omega$, the variables $d_i$ with $\mathrm{Tp}(\Sigma^l_Q)=\mathrm{Ts}_Q|_{d_i=c_{l+1+i}}$, and
$\Delta_\lambda=\det(d_{\lambda_i+j-i})$.

## K-theory

K-theoretic Thom polynomials are written in the Grothendieck expansion $g_\lambda$; the K-theoretic fundamental
class used is the class of the structure sheaf of a resolution, pushed forward
(see [K-theoretic Thom polynomials](k-theory.md)).

## Convention versions

Each data file records the convention it follows (`convention:` line). The labels used for now are
"TPP 2025" (Thom polynomials and SSM-Thom polynomials) and "TPP 2026" (Thom series, whose signs and orientations were
revised in 2026). *These labels are placeholders to be defined here.*
