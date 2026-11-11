export interface Amount {
  min: number;
  max: number;
}

export interface ParsedIngredient {
  prefix: string;
  amount?: Amount;
  unit?: string;
  name: string;
  head: string;
}

interface UnitInfo {
  canonical: string;
  plural?: string;
  base?: "g" | "ml";
  factor?: number;
}

const UNITS: Record<string, UnitInfo> = {
  mg: { canonical: "g", base: "g", factor: 0.001 },
  g: { canonical: "g", base: "g", factor: 1 },
  kg: { canonical: "g", base: "g", factor: 1000 },
  ml: { canonical: "ml", base: "ml", factor: 1 },
  cl: { canonical: "ml", base: "ml", factor: 10 },
  dl: { canonical: "ml", base: "ml", factor: 100 },
  l: { canonical: "ml", base: "ml", factor: 1000 },
  liter: { canonical: "ml", base: "ml", factor: 1000 },
  el: { canonical: "EL" },
  tl: { canonical: "TL" },
  msp: { canonical: "Msp." },
  "msp.": { canonical: "Msp." },
  prise: { canonical: "Prise", plural: "Prisen" },
  prisen: { canonical: "Prise", plural: "Prisen" },
  dose: { canonical: "Dose", plural: "Dosen" },
  dosen: { canonical: "Dose", plural: "Dosen" },
  bund: { canonical: "Bund" },
  "pck.": { canonical: "Pck." },
  "pkg.": { canonical: "Pck." },
  päckchen: { canonical: "Pck." },
  packung: { canonical: "Packung", plural: "Packungen" },
  packungen: { canonical: "Packung", plural: "Packungen" },
  stück: { canonical: "Stück" },
  "stk.": { canonical: "Stück" },
  zehe: { canonical: "Zehe", plural: "Zehen" },
  zehen: { canonical: "Zehe", plural: "Zehen" },
  scheibe: { canonical: "Scheibe", plural: "Scheiben" },
  scheiben: { canonical: "Scheibe", plural: "Scheiben" },
  becher: { canonical: "Becher" },
  glas: { canonical: "Glas", plural: "Gläser" },
  gläser: { canonical: "Glas", plural: "Gläser" },
  tasse: { canonical: "Tasse", plural: "Tassen" },
  tassen: { canonical: "Tasse", plural: "Tassen" },
  handvoll: { canonical: "Handvoll" },
  cm: { canonical: "cm" },
  blatt: { canonical: "Blatt" },
  würfel: { canonical: "Würfel" },
  zweig: { canonical: "Zweig", plural: "Zweige" },
  zweige: { canonical: "Zweig", plural: "Zweige" },
  stange: { canonical: "Stange", plural: "Stangen" },
  stangen: { canonical: "Stange", plural: "Stangen" },
  knolle: { canonical: "Knolle", plural: "Knollen" },
  knollen: { canonical: "Knolle", plural: "Knollen" },
};

const VULGAR: Record<string, number> = { "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75 };
const NUM = String.raw`\d+\s+\d+\/\d+|\d+\/\d+|\d+\s*[½⅓⅔¼¾]|\d+(?:[.,]\d+)?|[½⅓⅔¼¾]`;
const UNIT_ALT = Object.keys(UNITS)
  .sort((a, b) => b.length - a.length)
  .map((u) => u.replaceAll(".", String.raw`\.`))
  .join("|");
const LINE = new RegExp(
  String.raw`^((?:ca\.|etwa|circa)\s*)?(${NUM})(?:\s*[-–]\s*(${NUM}))?\s*(?:(${UNIT_ALT})(?=[\s,]|$))?\s*`,
  "iu",
);

export class Quantity {
  public static parseNumber(text: string): number {
    const t = text.trim().replace(",", ".");
    const mixed = /^(\d+)\s+(\d+)\/(\d+)$/.exec(t);
    if (mixed) {
      return Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
    }
    const fraction = /^(\d+)\/(\d+)$/.exec(t);
    if (fraction) {
      return Number(fraction[1]) / Number(fraction[2]);
    }
    const vulgar = /^(\d*)\s*([½⅓⅔¼¾])$/u.exec(t);
    if (vulgar) {
      return Number(vulgar[1] || 0) + VULGAR[vulgar[2]];
    }
    const n = Number(t);
    if (!Number.isFinite(n)) {
      throw new Error(`Menge nicht lesbar: "${text}"`);
    }
    return n;
  }

  public static parse(line: string): ParsedIngredient {
    const text = line.trim();
    const m = LINE.exec(text);
    if (!m) {
      return { prefix: "", name: text, head: "" };
    }
    const min = Quantity.parseNumber(m[2]);
    const max = m[3] ? Quantity.parseNumber(m[3]) : min;
    const unit = m[4] ? UNITS[m[4].toLowerCase()] : undefined;
    return {
      prefix: m[1] ? m[1].trim() : "",
      amount: { min, max },
      unit: unit ? m[4] : undefined,
      name: text.slice(m[0].length).trim(),
      head: m[0],
    };
  }

  public static unitInfo(unit: string | undefined): UnitInfo | undefined {
    return unit ? UNITS[unit.toLowerCase()] : undefined;
  }

  public static formatNumber(n: number, metric: boolean): string {
    if (!metric) {
      n = n < 10 ? Math.round(n * 12) / 12 : Math.round(n);
      const whole = Math.floor(n + 0.02);
      const rest = n - whole;
      const vulgar = Object.entries(VULGAR).find(([, v]) => Math.abs(v - rest) < 0.04);
      if (vulgar && rest > 0.04) {
        return `${whole > 0 ? whole : ""}${vulgar[0]}`;
      }
      if (Math.abs(rest) < 0.04) {
        return String(whole);
      }
    }
    return new Intl.NumberFormat("de-DE", { maximumFractionDigits: n < 10 ? 1 : 0 }).format(n);
  }

  public static roundMetric(n: number): number {
    if (n >= 100) {
      return Math.round(n / 5) * 5;
    }
    if (n >= 10) {
      return Math.round(n);
    }
    return Math.round(n * 10) / 10;
  }

  public static formatAmount(amount: Amount, unit: string | undefined): string {
    const info = Quantity.unitInfo(unit);
    if (info?.base) {
      const min = amount.min * (info.factor ?? 1);
      const max = amount.max * (info.factor ?? 1);
      const big = max >= 1000;
      const div = big ? 1000 : 1;
      const label = big ? (info.base === "g" ? "kg" : "l") : info.base;
      const fmt = (v: number): string =>
        big
          ? new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 }).format(v / div)
          : Quantity.formatNumber(Quantity.roundMetric(v), true);
      return `${fmt(min)}${min === max ? "" : `–${fmt(max)}`} ${label}`;
    }
    const num = `${Quantity.formatNumber(amount.min, false)}${amount.min === amount.max ? "" : `–${Quantity.formatNumber(amount.max, false)}`}`;
    if (!info) {
      return num;
    }
    const label = info.plural && amount.max > 1 ? info.plural : info.canonical;
    return `${num} ${label}`;
  }

  public static scale(amount: Amount, factor: number): Amount {
    return { min: amount.min * factor, max: amount.max * factor };
  }

  public static scaleText(text: string, factor: number): string {
    if (factor === 1) {
      return text;
    }
    return text.replace(new RegExp(`(${NUM})(?:\\s*[-–]\\s*(${NUM}))?`, "u"), (_all, a: string, b?: string) => {
      const min = Quantity.parseNumber(a) * factor;
      const fmt = (v: number): string => Quantity.formatNumber(v, false);
      return b ? `${fmt(min)}–${fmt(Quantity.parseNumber(b) * factor)}` : fmt(min);
    });
  }

  public static formatFactor(factor: number): string {
    return `${Quantity.formatNumber(factor, false)}×`;
  }
}
