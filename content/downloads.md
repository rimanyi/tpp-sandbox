---
title: Downloads
---

# Downloads

## All data

[**tpp-data.zip**](downloads/tpp-data.zip): every data file of the portal, in one archive (rebuilt automatically
whenever the data changes). Each file is plain text; the lines starting with `#` describe the contents, and the rest is
Maple input, so `read "tp_l2.txt":` defines the polynomials.

The same files can be downloaded one at a time from the singularity pages.

## RR's codes



<div class="wp-content" markdown="0">
<hr><strong>Double stable Grothendieck polynomials</strong>
- for partitions lambda with weight at most 11 
- k alpha variables at most 3
- l beta variables at most 4

For example lambda=[1], k=2, l=3: 1-(alpha[1]*alpha[2])/(beta[1]*beta[2]*beta[3])

<a href="@ROOT@/files/Double_Stable_Gr_polynomials.zip">Double_Stable_Gr_polynomials</a>

Usage: 
- download 
- unzip
- it will be one standalone file, with name Double_Stable_Gr_polynomials.m 
- in Maple code type  read "Double_Stable_Gr_polynomials.m";  (if you are in the right folder)
- k:=2: l:=3: lambda:=[3,1]: subs(GR[k,l], gr[lambda]);  will give the Grothendieck polynomial with k alpha and l beta variables.<hr>
</div>



## Files from the old site

PDF charts, pictures and code that were uploaded to the WordPress site.

<!-- TPP:downloads -->
