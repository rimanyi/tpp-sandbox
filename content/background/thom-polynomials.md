# What is a Thom polynomial


## Definition

<div class="wp-content" markdown="0">
Let \(G_n\) be the group of analytic diffeomorphism germs of \((C^n,0)\). Consider the vector space \(V_{n,n+l}=\{ f:(C^n,0)\to (C^{n+l},0)\) analytic\(\}\) acted upon by the group \(G_n \times G_{n+l}\), and let \(\Sigma\) be an invariant subset, the singularity.

The Thom polynomial of \(\Sigma\) is the \(G_n\times G_{n+l}\)-equivariant fundamental cohomology class of \(\overline{\Sigma}\), that is<p>Tp(\(\displaystyle \Sigma\))=\([\overline{\Sigma}\subset V_{n,n+l}] \in H^*_{G_n\times G_{n+l}}(V_{n,n+l})\).</p>Since \(G_n\) is homotopy equivalent to \(GL_n(C)\), and \(V_{n,n+l}\) is contractible, the Thom polynomial of \(\Sigma\) is a \(GL_n(C)\times GL_{n+l}(C)\)-characteristic class. Therefore, the Thom polynomial is a polynomial in the variables \(a_1,a_2,\ldots,a_n\), \(b_1,b_2,\ldots,b_{n+l}\), where \(a_i\) (\(b_i\)) is the i'th Chern class of the tautological bundle over \(BGL_n(C)\) (\(BGL_{n+l}(C)\)).
</div>

## Degeneracy locus interpretation

<div class="wp-content" markdown="0">
The Thom polynomial has the following <em>degeneracy locus</em> characterization. For a map \(f:N^n\to M^{n+l}\) (satisfying appropriate transversality properties) the cohomological fundamental class of the closure of \(\Sigma(f)=\{x\in N :\) the germ of \(f\) at \(x\) is from \(\Sigma \}\) is equal to the value of the Thom polynomial after substituting the Chern classes of N for \(a_i\) and the Chern classes of M (pulled back by \(f^*\)) for \(b_i\).
</div>

## Thom polynomials of contact singularities

<div class="wp-content" markdown="0">
An important class of singularities is the so-called <em>contact</em> singularities. One of their equivalent characterizations is the following. Let Q be a finite dimensional, local, commutative C-algebra. A contact singularity is \(\Sigma_Q=\{ f:(C^n,0)\to (C^{n+l},0) : Q_f\) is isomorphic with \(Q\}\), where the local algebra \(Q_f\) of the germ \(f=(f_1(x_1,\ldots,x_n),\ldots,f_{n+l}(x_1,\ldots,x_n))\) is defined by \(Q_f=C[[x_1,\ldots,x_n]]/(f_1,\ldots,f_{n+l})\). We often name the contact singularity by its local algebra or the ideal \((f_1,\ldots,f_{n+l})\).

It is a fact that the Thom polynomial of a contact singularity depends only on the ``quotient'' classes \(c_1,c_2,\ldots\), defined by the Taylor expansion \(({1+b_1t+b_2t^2+\ldots})/({1+a_1t+a_2t^2+\ldots})=1+c_1t+c_2t^2+\ldots\).
</div>

## Notation

<div class="wp-content" markdown="0">
For a partition \(\lambda=(\lambda_1,\ldots,\lambda_r)\) we define the Schur polynomial \(s_{\lambda}=\det(c_{\lambda_i+j-i})_{i,j=1,\ldots,r}\).<hr>
</div>


<p class="migrated">Migrated from the WordPress page <a href="https://tpp.web.unc.edu/ordinary-thom-polynomials/">ordinary-thom-polynomials</a> (last modified 2025-06-16).</p>
