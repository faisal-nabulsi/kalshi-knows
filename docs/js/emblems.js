// The Predator Scale emblems: hand-drawn geometric SVGs, one style.
// Animals for 2/3/5; typographic marks for the people tiers (1/4/6). No faces of real people.
const B = '#EDE8DF', B2 = '#D6CEC1', B3 = '#B9B1A4', K = '#0A0A0B', O = '#FF4D1A', O2 = '#FF7A4F', G = '#6F6B64';
const f = (n) => Math.round(n * 10) / 10;

// lion mane: 16-point faceted starburst
const mane = (() => {
  const c = [32, 33], pts = [];
  for (let k = 0; k < 16; k++) {
    const a = ((-90 + k * 22.5) * Math.PI) / 180, r = k % 2 ? 21.5 : 30.5;
    pts.push([c[0] + r * Math.cos(a), c[1] + r * Math.sin(a)]);
  }
  return pts.map((p, k) => {
    const q = pts[(k + 1) % 16];
    return `<path d="M${c[0]},${c[1]}L${f(p[0])},${f(p[1])}L${f(q[0])},${f(q[1])}Z" fill="${k % 2 ? B3 : B}" stroke="${K}" stroke-width=".7" stroke-linejoin="round"/>`;
  }).join('');
})();

const ART = {
  5: `<circle class="em-flash" cx="32" cy="33" r="30" fill="${O}" opacity="0"/>
    <g class="em-mane">${mane}</g>
    <path d="M21,19L24,11.5L28.5,16.5Z M43,19L40,11.5L35.5,16.5Z" fill="${B2}" stroke="${K}" stroke-width="1"/>
    <path d="M32,15L23,18L19,27L21,37L26,45L32,49Z" fill="${B}" stroke="${K}" stroke-width="1"/>
    <path d="M32,15L41,18L45,27L43,37L38,45L32,49Z" fill="${B2}" stroke="${K}" stroke-width="1"/>
    <path d="M24,25.5L30,27.8M40,25.5L34,27.8" stroke="${K}" stroke-width="1.7" stroke-linecap="square"/>
    <path class="em-eyes" d="M24.5,29L30,30L26.5,32.3Z M39.5,29L34,30L37.5,32.3Z" fill="${O}"/>
    <path d="M28.5,36H35.5L32,40.6Z" fill="${K}"/>
    <path d="M32,40.6V43.6M32,43.6L27.8,45.8M32,43.6L36.2,45.8" stroke="${K}" stroke-width="1.4" fill="none" stroke-linecap="round"/>`,
  3: `<g class="em-streaks" stroke="${O}" stroke-width="1.7" stroke-linecap="round"><path d="M3,24H13M1,29.5H10M5,35H11"/></g>
    <g class="em-gz">
      <path d="M17.5,31L13.5,27.8" stroke="${B}" stroke-width="2" stroke-linecap="round"/>
      <g stroke="${B2}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none">
        <path d="M22,35.5L13,39L5.5,42M26,37L17.5,42.5L11,48.5M44,35L51.5,38.5L57,44.5M40.5,36.5L48,41L52,47.5"/></g>
      <path d="M17,31L29,26L42,26.5L47,30L30,31.5Z" fill="${B}" stroke="${K}" stroke-width=".7"/>
      <path d="M17,31L30,31.5L47,30L44,36L31,37.5L20,36.5Z" fill="${B3}" stroke="${K}" stroke-width=".7"/>
      <path d="M20,33.6L44,32.6" stroke="${K}" stroke-width="1.5"/>
      <path d="M41,27L46,18.5L50.5,17.5L51.5,21L47,30Z" fill="${B}" stroke="${K}" stroke-width=".7"/>
      <path d="M48.5,16.5L54,13.5L60,17L57.5,19.6L51.5,20.6Z" fill="${B2}" stroke="${K}" stroke-width=".7"/>
      <path d="M49.5,15.5L46,11.5L51.5,13.6Z" fill="${B}" stroke="${K}" stroke-width=".6"/>
      <path d="M51,14C49.5,9 46.5,6 43,4.5M53.4,13.6C52.8,8.5 50.6,5 47.5,3" stroke="${B}" stroke-width="1.8" fill="none" stroke-linecap="round"/>
      <circle cx="55.2" cy="16.2" r=".95" fill="${K}"/>
    </g>`,
  2: `<path d="M5,51H59" stroke="#34343A" stroke-width="1.5"/>
    <g class="em-breath">
      <path d="M11,41L17,34.5L26,30.5L36,30L44,32.5L49,37L38,39L24,40Z" fill="${B}" stroke="${K}" stroke-width=".8"/>
      <path d="M9,50L11,41L24,40L38,39L49,37L49,50Z" fill="${B3}" stroke="${K}" stroke-width=".8"/>
    </g>
    <path d="M10,49.5C13,54 30,55.2 41,51.6" stroke="${B}" stroke-width="3.2" fill="none" stroke-linecap="round"/>
    <path d="M41.5,41L42.5,34L46.6,38.6Z M48,38.2L52.5,34L53.5,41Z" fill="${B2}" stroke="${K}" stroke-width=".9"/>
    <path d="M40,50.5L40.5,43L44,38.5L50,38L54,42L55,50.5Z" fill="${B}" stroke="${K}" stroke-width=".9"/>
    <path d="M43.4,44.6q1.6,1.4 3.2,0M48.6,44.6q1.6,1.4 3.2,0" stroke="${K}" stroke-width="1.2" fill="none" stroke-linecap="round"/>
    <path d="M46.6,46.8H48.6L47.6,48Z" fill="${O}"/>
    <g class="em-z" fill="${O}" font-family="IBM Plex Mono, monospace" font-weight="700"><text x="50" y="27" font-size="7">z</text><text x="55" y="19" font-size="9.5">z</text></g>`,
  6: `<g class="em-crown">
      <path d="M13,36L10,17L21,26L32,11L43,26L54,17L51,36Z" fill="${O}" stroke="${K}" stroke-width=".9" stroke-linejoin="round"/>
      <path d="M21,26L32,11L32,36Z M43,26L54,17L51,36Z" fill="${O2}"/>
      <rect x="13" y="35.5" width="38" height="6.5" fill="${B}" stroke="${K}" stroke-width=".9"/>
      <circle cx="20" cy="38.8" r="1.4" fill="${K}"/><circle cx="32" cy="38.8" r="1.4" fill="${K}"/><circle cx="44" cy="38.8" r="1.4" fill="${K}"/>
    </g>
    <g class="em-stamp"><g transform="rotate(-7 32 53)">
      <rect x="6.5" y="45.5" width="51" height="14" fill="${K}" stroke="${B}" stroke-width="1.5"/>
      <text x="32" y="51.6" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="5" fill="${B}" letter-spacing=".4">RETURNED</text>
      <text x="32" y="57.4" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="4.6" fill="${O}" letter-spacing=".3">THE FUND ×2</text>
    </g></g>`,
  1: `<g class="em-ticket" transform="rotate(-9 32 32)">
      <path d="M7,19H57V28A4,4 0 0 0 57,36V45H7V36A4,4 0 0 0 7,28Z" fill="#18181B" stroke="${B3}" stroke-width="1.4"/>
      <path d="M43,20.5V43.5" stroke="${G}" stroke-width="1" stroke-dasharray="2 2"/>
      <text x="25" y="31.5" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="6.2" fill="${B2}">WAITLIST</text>
      <text x="25" y="39" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="4.4" fill="${G}">NO. 4,812</text>
      <text x="50" y="34.5" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="7" fill="${G}">0</text>
    </g>`,
  4: `<g class="em-decks">
      <rect class="em-d3" x="16" y="10" width="40" height="26" fill="#141416" stroke="${G}" stroke-width="1.2"/>
      <rect class="em-d2" x="11" y="16" width="40" height="26" fill="#18181B" stroke="${B3}" stroke-width="1.2"/>
      <g class="em-d1"><rect x="6" y="22" width="40" height="26" fill="#111113" stroke="${B}" stroke-width="1.5"/>
        <path d="M10,28H31" stroke="${B}" stroke-width="2"/>
        <path d="M10,33.5H38M10,37.5H34M10,41.5H27" stroke="${G}" stroke-width="1.3"/>
        <text x="43" y="45.6" text-anchor="end" font-family="IBM Plex Mono, monospace" font-size="3.6" fill="${B3}">1/40</text></g>
    </g>
    <text x="32" y="58" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="4.3" fill="${G}" letter-spacing=".3">40 SLIDES · 0 ANSWERS</text>`,
};

export function emblem(tier, cls = '') {
  const t = Math.min(6, Math.max(1, tier | 0));
  return `<svg class="em em-${t} ${cls}" viewBox="0 0 64 64" aria-hidden="true" focusable="false">${ART[t]}</svg>`;
}
