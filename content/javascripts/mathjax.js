window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: "tpp-nomath"
  }
};

document$.subscribe(() => {
  if (window.MathJax && MathJax.typesetPromise) {
    if (MathJax.startup.output && MathJax.startup.output.clearCache) MathJax.startup.output.clearCache();
    MathJax.typesetClear();
    MathJax.texReset();
    MathJax.typesetPromise();
  }
});
