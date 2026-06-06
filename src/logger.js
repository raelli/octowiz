// ⊛ — Octowiz terminal logger
// Bold indigo ⊛ on white background on every line so Octowiz output is instantly identifiable.

const BOLD     = '\x1b[1m';
const PURPLE   = '\x1b[38;5;135m';  // #AF5FFF
const DIM      = '\x1b[2m';
const YELLOW   = '\x1b[38;5;220m';
const RED      = '\x1b[38;5;203m';
const RESET    = '\x1b[0m';

const BADGE_OCW   = `${BOLD}${PURPLE}[--*]${RESET}`;
const BADGE_AELLI = `${BOLD}${PURPLE}[æ]${RESET}`;

function badge(args) {
  const first = typeof args[0] === 'string' ? args[0] : '';
  return /\[AELLI/i.test(first) ? BADGE_AELLI : BADGE_OCW;
}

function ts() {
  return `${DIM}${new Date().toISOString().slice(11, 19)}${RESET}`;
}

function tag(str) {
  if (typeof str !== 'string') return str;
  return str.replace(/\[[^\]]+\]/g, (m) => `${PURPLE}${m}${RESET}`);
}

function fmt(args) { return [tag(args[0]), ...args.slice(1)]; }

const log   = (...args) => console.error(`${badge(args)} ${ts()}`, ...fmt(args));
const info  = (...args) => console.error(`${badge(args)} ${ts()}`, ...fmt(args));
const warn  = (...args) => console.warn (`${badge(args)} ${ts()} ${YELLOW}warn${RESET}`, ...fmt(args));
const error = (...args) => console.error(`${badge(args)} ${ts()} ${RED}err${RESET} `, ...fmt(args));

module.exports = { log, info, warn, error };
