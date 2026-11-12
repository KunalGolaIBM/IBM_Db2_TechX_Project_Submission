/**
 * Shippy, the ShipSafe mascot: the yellow shield from the logo with a captain's cap.
 * Pure SVG strings (no assets to load), one per mood, so the sidebar can react to results.
 */
export type Mood = "happy" | "alert" | "thinking" | "celebrate" | "sleepy";

const INK = "#141414";
const GOLD = "#F2C94C";
const GOLD_DARK = "#D9A92B";
const BLUE = "#3B6CFF";

function eyes(mood: Mood): string {
  switch (mood) {
    case "celebrate":
      return `<path d="M70 108 q10 -14 20 0 M110 108 q10 -14 20 0" stroke="#fff" stroke-width="6" fill="none" stroke-linecap="round"/>`;
    case "sleepy":
      return `<path d="M70 106 q10 8 20 0 M110 106 q10 8 20 0" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round"/>`;
    case "alert":
      return `<ellipse cx="80" cy="104" rx="10" ry="14" fill="#fff"/><ellipse cx="120" cy="104" rx="10" ry="14" fill="#fff"/>` +
        `<circle cx="80" cy="104" r="4.5" fill="${INK}"/><circle cx="120" cy="104" r="4.5" fill="${INK}"/>`;
    case "thinking":
      return `<ellipse cx="80" cy="104" rx="9" ry="12" fill="#fff"/><ellipse cx="120" cy="104" rx="9" ry="12" fill="#fff"/>` +
        `<circle cx="84" cy="98" r="4.5" fill="${INK}"/><circle cx="124" cy="98" r="4.5" fill="${INK}"/>`;
    default:
      return `<ellipse cx="80" cy="104" rx="9" ry="12" fill="#fff"/><ellipse cx="120" cy="104" rx="9" ry="12" fill="#fff"/>` +
        `<circle cx="82" cy="100" r="3" fill="${BLUE}"/><circle cx="122" cy="100" r="3" fill="${BLUE}"/>`;
  }
}

function mouth(mood: Mood): string {
  switch (mood) {
    case "celebrate":
      return `<path d="M84 146 q16 22 32 0 z" fill="${INK}"/><path d="M92 153 q8 6 16 0" fill="#E9616A"/>`;
    case "alert":
      return `<ellipse cx="100" cy="151" rx="7" ry="8" fill="${INK}"/>`;
    case "thinking":
      return `<path d="M90 150 h20" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>`;
    case "sleepy":
      return `<path d="M92 150 q8 5 16 0" stroke="${INK}" stroke-width="4" fill="none" stroke-linecap="round"/>`;
    default:
      return `<path d="M86 146 q14 14 28 0" stroke="${INK}" stroke-width="5" fill="none" stroke-linecap="round"/>`;
  }
}

function extras(mood: Mood): string {
  switch (mood) {
    case "alert":
      return `<g transform="translate(160 40)"><circle r="17" fill="#E5484D" stroke="${INK}" stroke-width="4"/>` +
        `<path d="M0 -8 v9" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cy="8" r="3" fill="#fff"/></g>`;
    case "thinking":
      return `<g fill="${BLUE}"><circle cx="152" cy="52" r="5"/><circle cx="166" cy="40" r="6.5"/><circle cx="182" cy="24" r="8"/></g>`;
    case "celebrate":
      return `<g fill="${GOLD}" stroke="${INK}" stroke-width="2.5" stroke-linejoin="round">` +
        `<path d="M22 40 l4 9 9 4 -9 4 -4 9 -4 -9 -9 -4 9 -4z"/><path d="M174 30 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z"/></g>`;
    case "sleepy":
      return `<g fill="${BLUE}" font-family="Arial, sans-serif" font-weight="700"><text x="150" y="44" font-size="20">z</text>` +
        `<text x="166" y="28" font-size="14">z</text></g>`;
    default:
      return "";
  }
}

function arms(mood: Mood): string {
  const wave = mood === "celebrate" || mood === "happy";
  const left = wave
    ? `<path d="M36 120 q-22 -14 -18 -40" stroke="${INK}" stroke-width="13" fill="none" stroke-linecap="round"/>` +
      `<path d="M36 120 q-22 -14 -18 -40" stroke="${GOLD}" stroke-width="7" fill="none" stroke-linecap="round"/>`
    : `<path d="M36 124 q-18 10 -16 30" stroke="${INK}" stroke-width="13" fill="none" stroke-linecap="round"/>` +
      `<path d="M36 124 q-18 10 -16 30" stroke="${GOLD}" stroke-width="7" fill="none" stroke-linecap="round"/>`;
  const rightUp = mood === "celebrate" || mood === "thinking";
  const right = rightUp
    ? `<path d="M164 120 q22 -14 18 -40" stroke="${INK}" stroke-width="13" fill="none" stroke-linecap="round"/>` +
      `<path d="M164 120 q22 -14 18 -40" stroke="${GOLD}" stroke-width="7" fill="none" stroke-linecap="round"/>`
    : `<path d="M164 124 q18 10 16 30" stroke="${INK}" stroke-width="13" fill="none" stroke-linecap="round"/>` +
      `<path d="M164 124 q18 10 16 30" stroke="${GOLD}" stroke-width="7" fill="none" stroke-linecap="round"/>`;
  return left + right;
}

/** Shippy as an SVG string. `size` is the rendered width in px. */
export function mascotSvg(mood: Mood = "happy", size = 120, title = "Shippy, the ShipSafe guide"): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 224" width="${size}" height="${Math.round(size * 1.12)}" role="img" aria-label="${title}">
<title>${title}</title>
<ellipse cx="100" cy="214" rx="54" ry="8" fill="${INK}" opacity="0.18"/>
${arms(mood)}
<path d="M100 44 C128 54 150 56 166 56 L166 118 C166 164 134 192 100 206 C66 192 34 164 34 118 L34 56 C50 56 72 54 100 44 Z" fill="${GOLD}" stroke="${INK}" stroke-width="6" stroke-linejoin="round"/>
<path d="M100 56 C124 64 142 66 154 66 L154 118 C154 156 128 180 100 192" fill="none" stroke="${GOLD_DARK}" stroke-width="6" stroke-linecap="round" opacity="0.7"/>
<rect x="56" y="82" width="88" height="48" rx="24" fill="${INK}"/>
${eyes(mood)}
<circle cx="62" cy="142" r="7" fill="#F28B82" opacity="0.55"/><circle cx="138" cy="142" r="7" fill="#F28B82" opacity="0.55"/>
${mouth(mood)}
<path d="M86 172 l10 10 l18 -18" stroke="${INK}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M56 42 C52 12 148 12 144 42 Z" fill="#F7F7F2" stroke="${INK}" stroke-width="5" stroke-linejoin="round"/>
<rect x="56" y="33" width="88" height="8" rx="3" fill="${BLUE}"/>
<rect x="48" y="40" width="104" height="13" rx="6.5" fill="${INK}"/>
<circle cx="100" cy="27" r="9" fill="${GOLD}" stroke="${INK}" stroke-width="3"/>
<path d="M95.5 27 l3 3 l6 -6" stroke="${INK}" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
${extras(mood)}
</svg>`;
}
