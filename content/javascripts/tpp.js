// Copy buttons on Maple blocks
document$.subscribe(() => {
  document.querySelectorAll("pre.maple").forEach((pre) => {
    if (pre.dataset.copy) return;
    pre.dataset.copy = "1";
    const btn = document.createElement("button");
    btn.className = "tpp-copy";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", (ev) => {
      ev.preventDefault();
      const text = pre.firstChild && pre.firstChild.nodeType === 3 ? pre.firstChild.textContent : pre.innerText.replace(/Copy(ed)?$/, "");
      navigator.clipboard.writeText(text.trim()).then(() => {
        btn.textContent = "Copied";
        setTimeout(() => (btn.textContent = "Copy"), 1500);
      }).catch(() => {
        const r = document.createRange(); r.selectNodeContents(pre);
        const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      });
    });
    pre.appendChild(btn);
  });
});
