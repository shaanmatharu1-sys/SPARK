// lib/navigation.js — single source of truth for page metadata, replacing
// the flat TABS array App.jsx used to render as a horizontal tab strip.
// Same 24 page ids/labels as before (no page was renamed or dropped),
// just grouped into categories for the new SideMenu, plus a lookup of
// real Bloomberg mnemonic codes for the ones that have a genuine landing
// spot here — used by CommandBar to resolve e.g. "OMON" -> the options page.

export const CATEGORIES = [
  {
    label: 'Markets',
    pages: [
      { id: 'overview',   label: 'Overview' },
      { id: 'markets',    label: 'Markets' },
      { id: 'world',      label: 'World' },
      { id: 'futures',    label: 'Futures' },
      { id: 'multichart', label: 'Multi-Chart' },
      { id: 'supply',     label: 'Supply Routes' },
      { id: 'news',       label: 'News' },
    ],
  },
  {
    label: 'Economy',
    pages: [
      { id: 'macro',  label: 'Macro' },
      { id: 'yield',  label: 'Yield / Rates' },
      { id: 'credit', label: 'Credit' },
      { id: 'regime', label: 'Regime' },
      { id: 'events', label: 'Events' },
    ],
  },
  {
    label: 'Equity Research',
    pages: [
      { id: 'research', label: 'Research' },
      { id: 'whales',   label: 'Whales' },
      { id: 'network',  label: 'Network' },
      { id: 'ties',     label: 'Ties' },
    ],
  },
  {
    label: 'Options & Quant',
    pages: [
      { id: 'options',  label: 'Options' },
      { id: 'quant',    label: 'Quant' },
      { id: 'backtest', label: 'Backtest' },
      { id: 'algo',     label: 'Algo' },
      { id: 'graph',    label: 'Graph Builder' },
    ],
  },
  {
    label: 'Alternative Data',
    pages: [
      { id: 'altdata', label: 'Alt-Data' },
      { id: 'arb',     label: 'Arbitrage' },
    ],
  },
  {
    label: 'Portfolio & Tools',
    pages: [
      { id: 'portfolio', label: 'Portfolio' },
    ],
  },
]

// Flat lookup, same shape the old TABS array had — kept for anywhere that
// wants "all pages" without the category grouping (e.g. CommandBar search).
export const ALL_PAGES = CATEGORIES.flatMap(c => c.pages)

export function pageLabel(id) {
  return ALL_PAGES.find(p => p.id === id)?.label || id
}

// Real Bloomberg function codes that have a genuine landing spot in this
// app today. Deliberately incomplete — codes with no backing feature
// (BLAW, WEAT, MSGM, ...) are left out so the command bar falls through
// to an honest "no page match" rather than pretending a page exists.
export const MNEMONIC_ALIASES = {
  MAIN: 'overview',
  N: 'news', TOP: 'news', CN: 'news', BBEA: 'news',
  BTMM: 'macro', ECST: 'macro', FED: 'macro', FOMC: 'macro', OECD: 'macro',
  ECO: 'events', ECDR: 'events',
  FXIP: 'world', FXC: 'world', WEI: 'world', WEIF: 'world', IMAP: 'world', CBQ: 'world',
  IMOV: 'markets', MOST: 'markets', DES: 'markets', BQ: 'markets', HP: 'markets',
  HCPI: 'markets', DVD: 'markets', CACS: 'markets', ANR: 'markets', ERN: 'markets',
  EE: 'markets', EM: 'markets', CF: 'markets', RELS: 'markets', HDS: 'markets',
  RV: 'markets', FA: 'markets', SRCH: 'markets', NW: 'markets', BLP: 'markets',
  GRR: 'research', MRR: 'research', BETA: 'research', CORR: 'research', OVME: 'research',
  OMON: 'options', HIVG: 'options',
  GP: 'graph', GPO: 'graph', GIP: 'graph', GEG: 'graph', G: 'graph',
  COMP: 'multichart',
  YCRV: 'yield', CURV: 'yield', FWCV: 'yield', BBT: 'yield', PX1: 'yield',
  YA: 'yield', YAS: 'yield', OAS1: 'yield', WB: 'yield', WBF: 'yield', WBI: 'yield',
  CRPR: 'credit', GCDS: 'credit', WCDS: 'credit', CDSD: 'credit', DDIS: 'credit',
  NIM: 'credit', PICK: 'credit', STGO: 'credit', MTAX: 'credit', MYC: 'credit', RATC: 'credit',
}
