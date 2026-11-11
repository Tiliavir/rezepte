import { type Amount, Quantity } from "./lib/quantity";
import { Store } from "./lib/store";
import { Toast } from "./lib/toast";

interface ScaledLine {
  element: HTMLElement;
  original: string;
  amount: Amount;
  unit?: string;
  prefix: string;
}

interface WakeLockSentinelLike {
  release(): Promise<void>;
  addEventListener(type: "release", listener: () => void): void;
}

const FACTORS = [0.25, 0.5, 1, 1.5, 2, 3, 4, 6, 8];

export class Recipe {
  private static lines: ScaledLine[] = [];
  private static factor = 1;
  private static ref = "";
  private static wakeLock: WakeLockSentinelLike | null = null;

  public static initialize(article: HTMLElement): void {
    Recipe.ref = article.dataset.recipe ?? "";
    Recipe.markAmounts(article);
    Recipe.initScaler(article);
    Recipe.initAddToList(article);
    Recipe.initWakeLock(article);
    Recipe.initPrint(article);
    Recipe.initStepsDone(article);
  }

  private static markAmounts(article: HTMLElement): void {
    for (const element of article.querySelectorAll<HTMLElement>("[data-ingredient]")) {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const first = walker.nextNode() as Text | null;
      if (!first?.data.trim()) {
        continue;
      }
      const leading = first.data.length - first.data.trimStart().length;
      const parsed = Quantity.parse(first.data);
      if (!parsed.amount) {
        continue;
      }
      const original = first.data.slice(leading, leading + parsed.head.length).trimEnd();
      const span = document.createElement("span");
      span.className = "amount";
      span.textContent = original;
      const rest = first.splitText(leading);
      rest.data = rest.data.slice(original.length);
      rest.before(span);
      Recipe.lines.push({ element: span, original, amount: parsed.amount, unit: parsed.unit, prefix: parsed.prefix });
    }
  }

  private static initScaler(article: HTMLElement): void {
    const panel = article.querySelector<HTMLElement>("[data-scaler]");
    const control = panel?.querySelector<HTMLElement>("[data-scaler-control]");
    const output = panel?.querySelector<HTMLOutputElement>("[data-scale-output]");
    if (!panel || !control || !output || Recipe.lines.length === 0) {
      return;
    }
    const yieldText = panel.dataset.yield ?? "";
    const yieldTarget = article.querySelector<HTMLElement>("[data-yield-text]");
    // step by single servings only for "4 Portionen"-like yields; "16 Buns" or "1 Kuchen" scale by factor
    const servings = /^(\d+)\s+Portion/.exec(yieldText);
    const base = servings ? Number(servings[1]) : 0;

    const stored = Store.load().recipes[Recipe.ref];
    Recipe.factor = stored ?? 1;

    const render = (): void => {
      output.value = base ? String(Math.round(Recipe.factor * base)) : Quantity.formatFactor(Recipe.factor);
      if (yieldTarget) {
        yieldTarget.textContent = Quantity.scaleText(yieldText, Recipe.factor);
      }
      for (const line of Recipe.lines) {
        line.element.textContent =
          Recipe.factor === 1
            ? line.original
            : `${line.prefix ? `${line.prefix} ` : ""}${Quantity.formatAmount(Quantity.scale(line.amount, Recipe.factor), line.unit)}`;
        line.element.classList.toggle("is-scaled", Recipe.factor !== 1);
      }
    };

    for (const button of control.querySelectorAll<HTMLButtonElement>("[data-scale]")) {
      button.addEventListener("click", () => {
        const direction = Number(button.dataset.scale);
        if (base) {
          const next = Math.max(1, Math.round(Recipe.factor * base) + direction);
          Recipe.factor = next / base;
        } else {
          const index = FACTORS.findIndex((f) => f >= Recipe.factor - 1e-9);
          Recipe.factor = FACTORS[Math.min(FACTORS.length - 1, Math.max(0, index + direction))];
        }
        render();
        Recipe.syncStoredFactor();
      });
    }
    control.hidden = false;
    render();
  }

  private static syncStoredFactor(): void {
    try {
      const state = Store.load();
      if (state.recipes[Recipe.ref] !== undefined) {
        state.recipes[Recipe.ref] = Recipe.factor;
        Store.save(state);
      }
    } catch (error) {
      Toast.error(error);
    }
  }

  private static initAddToList(article: HTMLElement): void {
    const button = article.querySelector<HTMLButtonElement>("[data-add-to-list]");
    const label = button?.querySelector<HTMLElement>("[data-add-label]");
    if (!button || !label || !Recipe.ref) {
      return;
    }
    const render = (): void => {
      const onList = Store.load().recipes[Recipe.ref] !== undefined;
      button.setAttribute("aria-pressed", String(onList));
      button.classList.toggle("is-done", onList);
      button.classList.toggle("button--primary", !onList);
      label.textContent = onList ? "Auf der Einkaufsliste" : "Auf die Einkaufsliste";
    };
    button.addEventListener("click", () => {
      try {
        const state = Store.update((s) => {
          if (s.recipes[Recipe.ref] === undefined) {
            s.recipes[Recipe.ref] = Recipe.factor;
          } else {
            delete s.recipes[Recipe.ref];
          }
        });
        Toast.show(
          state.recipes[Recipe.ref] === undefined ? "Von der Einkaufsliste entfernt" : "Zur Einkaufsliste hinzugefügt",
        );
      } catch (error) {
        Toast.error(error);
      }
      render();
    });
    Store.onChange(render);
    button.hidden = false;
    render();
  }

  private static initWakeLock(article: HTMLElement): void {
    const button = article.querySelector<HTMLButtonElement>("[data-wake-lock]");
    const wakeLock = (
      navigator as Navigator & { wakeLock?: { request(type: "screen"): Promise<WakeLockSentinelLike> } }
    ).wakeLock;
    if (!button || !wakeLock) {
      return;
    }
    let wanted = false;
    const set = (active: boolean): void => {
      button.setAttribute("aria-pressed", String(active));
      document.body.classList.toggle("is-cooking", active);
    };
    const acquire = async (): Promise<void> => {
      Recipe.wakeLock = await wakeLock.request("screen");
      Recipe.wakeLock.addEventListener("release", () => set(false));
      set(true);
    };
    button.addEventListener("click", () => {
      wanted = !wanted;
      if (wanted) {
        acquire().catch((error: unknown) => {
          wanted = false;
          Toast.error(error);
        });
      } else {
        Recipe.wakeLock?.release().catch(Toast.error);
        Recipe.wakeLock = null;
      }
    });
    document.addEventListener("visibilitychange", () => {
      if (wanted && document.visibilityState === "visible") {
        acquire().catch(Toast.error);
      }
    });
    button.hidden = false;
  }

  private static initPrint(article: HTMLElement): void {
    const button = article.querySelector<HTMLButtonElement>("[data-print]");
    if (!button) {
      return;
    }
    button.addEventListener("click", () => window.print());
    button.hidden = false;
  }

  private static initStepsDone(article: HTMLElement): void {
    const done = article.querySelector<HTMLElement>("[data-steps-done]");
    const boxes = [...article.querySelectorAll<HTMLInputElement>(".step-list input")];
    if (!done || boxes.length === 0) {
      return;
    }
    for (const box of boxes) {
      box.addEventListener("change", () => {
        done.hidden = !boxes.every((b) => b.checked);
      });
    }
  }
}
