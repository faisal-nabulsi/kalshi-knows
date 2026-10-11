// QR code as crisp SVG, via the tiny qrcode-generator library (pinned CDN).
export async function qrSVG(text, { margin = 2 } = {}) {
  const mod = await import('https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/+esm');
  const qrcode = mod.default || mod;
  const q = qrcode(0, 'M'); q.addData(text); q.make();
  const n = q.getModuleCount(), s = n + margin * 2;
  let d = '';
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c)) d += `M${c + margin},${r + margin}h1v1h-1z`;
  return `<svg viewBox="0 0 ${s} ${s}" shape-rendering="crispEdges" role="img" aria-label="QR code for ${text}"><rect width="${s}" height="${s}" fill="#EDE8DF"/><path d="${d}" fill="#0A0A0B"/></svg>`;
}
