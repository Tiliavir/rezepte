import { AISLE_ORDER, Aisles } from "./lib/aisles";
import { type Amount, Quantity } from "./lib/quantity";
import { type ShoppingState, Store } from "./lib/store";
import { Toast } from "./lib/toast";

interface RecipeData {
  ref: string;
  url: string;
  title: string;
  yield: string;
  ingredients: string[];
}

interface Item {
  key: string;
  aisle: string;
  name: string;
  amounts: Map<string, { amount: Amount; unit?: string }>;
  sources: Set<string>;
  extraId?: string;
}

export class ShoppingList {
  private static recipes = new Map<string, RecipeData>();
  private static root: HTMLElement;

  public static initialize(root: HTMLElement): void {
    ShoppingList.root = root;
    const data = document.getElementById("recipe-data")?.textContent;
    if (!data) {
      throw new Error("Rezeptdaten für die Einkaufsliste fehlen.");
    }
    for (const recipe of JSON.parse(data) as RecipeData[]) {
      ShoppingList.recipes.set(recipe.ref, recipe);
    }

    ShoppingList.initPicker();
    ShoppingList.initForm();
    ShoppingList.initActions();
    root.addEventListener("change", (e) => ShoppingList.onCheck(e));
    root.addEventListener("click", (e) => ShoppingList.onClick(e));
    Store.onChange(() => ShoppingList.render());
    ShoppingList.render();
  }

  private static q<T extends HTMLElement>(selector: string): T {
    const element = ShoppingList.root.querySelector<T>(selector);
    if (!element) {
      throw new Error(`Element ${selector} fehlt auf der Einkaufslisten-Seite.`);
    }
    return element;
  }

  private static initPicker(): void {
    const filter = ShoppingList.q<HTMLInputElement>("[data-picker-filter]");
    const items = [...ShoppingList.q("[data-picker]").querySelectorAll<HTMLLIElement>("li")];
    filter.addEventListener("input", () => {
      const term = filter.value.trim().toLowerCase();
      for (const li of items) {
        li.hidden = term !== "" && !(li.dataset.title ?? "").includes(term);
      }
    });
    for (const li of items) {
      const ref = li.dataset.ref ?? "";
      if (!ShoppingList.recipes.has(ref)) {
        throw new Error(`Rezept ${ref} fehlt in den Rezeptdaten.`);
      }
      li.querySelector<HTMLButtonElement>("[data-pick]")?.addEventListener("click", () => {
        ShoppingList.safe(() =>
          Store.update((s) => {
            if (s.recipes[ref] === undefined) {
              s.recipes[ref] = 1;
            } else {
              delete s.recipes[ref];
            }
          }),
        );
      });
    }
  }

  private static initForm(): void {
    const form = ShoppingList.q<HTMLFormElement>("[data-add-item]");
    const input = form.querySelector<HTMLInputElement>("input");
    if (!input) {
      throw new Error("Eingabefeld für eigene Einträge fehlt.");
    }
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) {
        return;
      }
      ShoppingList.safe(() =>
        Store.update((s) => {
          s.extras.unshift({ id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, text });
        }),
      );
      input.value = "";
      input.focus();
    });
  }

  private static initActions(): void {
    const clear = ShoppingList.q<HTMLButtonElement>("[data-clear]");
    const label = clear.querySelector("span");
    let armed = 0;
    clear.addEventListener("click", () => {
      if (!armed) {
        if (label) {
          label.textContent = "Wirklich leeren?";
        }
        armed = window.setTimeout(() => {
          armed = 0;
          if (label) {
            label.textContent = "Leeren";
          }
        }, 3000);
        return;
      }
      window.clearTimeout(armed);
      armed = 0;
      if (label) {
        label.textContent = "Leeren";
      }
      ShoppingList.safe(() => Store.save(Store.empty()));
    });

    ShoppingList.q("[data-clear-done]").addEventListener("click", () => {
      ShoppingList.safe(() =>
        Store.update((s) => {
          const done = new Set(s.checked);
          s.extras = s.extras.filter((x) => !done.has(`x:${x.id}`));
          for (const ref of Object.keys(s.recipes)) {
            const recipe = ShoppingList.recipes.get(ref);
            const keys = recipe ? recipe.ingredients.map((line) => ShoppingList.keyOf(Quantity.parse(line).name)) : [];
            if (keys.length > 0 && keys.every((k) => done.has(k))) {
              delete s.recipes[ref];
            }
          }
          s.checked = [...done].filter((k) => !k.startsWith("x:"));
        }),
      );
    });

    ShoppingList.q<HTMLButtonElement>("[data-share]").addEventListener("click", () => {
      const state = Store.load();
      const items = ShoppingList.items(state);
      const open = items.filter((i) => !state.checked.includes(i.key));
      const text = [
        "Einkaufsliste",
        ...AISLE_ORDER.flatMap((aisle) => {
          const group = open.filter((i) => i.aisle === aisle);
          return group.length ? ["", `${aisle}:`, ...group.map((i) => `☐ ${ShoppingList.label(i)}`)] : [];
        }),
      ].join("\n");
      if (navigator.share) {
        navigator.share({ title: "Einkaufsliste", text }).catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === "AbortError")) {
            Toast.error(error);
          }
        });
      } else {
        navigator.clipboard
          .writeText(text)
          .then(() => Toast.show("Liste in die Zwischenablage kopiert"))
          .catch(Toast.error);
      }
    });
  }

  private static onCheck(e: Event): void {
    const box = e.target;
    if (!(box instanceof HTMLInputElement) || !box.dataset.key) {
      return;
    }
    const key = box.dataset.key;
    const checked = box.checked;
    window.setTimeout(() => {
      ShoppingList.safe(() =>
        Store.update((s) => {
          s.checked = s.checked.filter((k) => k !== key);
          if (checked) {
            s.checked.push(key);
          }
        }),
      );
    }, 250);
  }

  private static onClick(e: Event): void {
    const target = e.target instanceof Element ? e.target.closest<HTMLButtonElement>("button[data-action]") : null;
    if (!target) {
      return;
    }
    const { action, ref, id } = target.dataset;
    ShoppingList.safe(() =>
      Store.update((s) => {
        if (action === "remove-extra" && id) {
          s.extras = s.extras.filter((x) => x.id !== id);
          s.checked = s.checked.filter((k) => k !== `x:${id}`);
        } else if (ref && s.recipes[ref] !== undefined) {
          if (action === "remove-recipe") {
            delete s.recipes[ref];
          } else {
            const step = action === "more" ? 0.5 : -0.5;
            s.recipes[ref] = Math.max(0.5, s.recipes[ref] + step);
          }
        }
      }),
    );
  }

  private static safe(fn: () => unknown): void {
    try {
      fn();
    } catch (error) {
      Toast.error(error);
    }
  }

  private static keyOf(name: string): string {
    const words = name.split(",")[0].trim().toLowerCase().split(/\s+/);
    const last = words.length - 1;
    // naive German plural folding so "Zwiebel" and "Zwiebeln", "Karotte" and "Karotten" end up together
    words[last] = words[last].replace(/(?<=[elr])n$/, "").replace(/(?<=e)n$/, "");
    return words.join(" ");
  }

  private static items(state: ShoppingState): Item[] {
    const items = new Map<string, Item>();
    for (const [ref, factor] of Object.entries(state.recipes)) {
      const recipe = ShoppingList.recipes.get(ref);
      if (!recipe) {
        continue;
      }
      for (const line of recipe.ingredients) {
        const parsed = Quantity.parse(line);
        if (!parsed.name) {
          continue;
        }
        const aisle = Aisles.of(parsed.name);
        if (aisle === null) {
          continue;
        }
        const key = ShoppingList.keyOf(parsed.name);
        const item = items.get(key) ?? {
          key,
          aisle,
          name: parsed.name.split(",")[0].trim(),
          amounts: new Map(),
          sources: new Set<string>(),
        };
        const display = parsed.name.split(",")[0].trim();
        if (display.length > item.name.length) {
          item.name = display;
        }
        item.sources.add(recipe.title);
        if (parsed.amount) {
          const info = Quantity.unitInfo(parsed.unit);
          const unitKey = info?.base ?? info?.canonical ?? "";
          const scaled = Quantity.scale(parsed.amount, factor * (info?.factor ?? 1));
          const existing = item.amounts.get(unitKey);
          item.amounts.set(unitKey, {
            amount: existing
              ? { min: existing.amount.min + scaled.min, max: existing.amount.max + scaled.max }
              : scaled,
            unit: unitKey || undefined,
          });
        }
        items.set(key, item);
      }
    }
    const sorted = [...items.values()].sort((a, b) => a.name.localeCompare(b.name, "de"));
    const extras: Item[] = state.extras.map((x) => {
      const parsed = Quantity.parse(x.text);
      const amounts = new Map<string, { amount: Amount; unit?: string }>();
      if (parsed.amount && parsed.name) {
        amounts.set("", { amount: parsed.amount, unit: parsed.unit });
      }
      const name = amounts.size ? parsed.name : x.text;
      return {
        key: `x:${x.id}`,
        aisle: Aisles.of(name) ?? "Sonstiges",
        name,
        amounts,
        sources: new Set(["Eigener Eintrag"]),
        extraId: x.id,
      };
    });
    return [...extras, ...sorted];
  }

  private static amountText(item: Item): string {
    return [...item.amounts.values()].map((a) => Quantity.formatAmount(a.amount, a.unit)).join(" + ");
  }

  private static label(item: Item): string {
    const amount = ShoppingList.amountText(item);
    return amount ? `${amount} ${item.name}` : item.name;
  }

  private static render(): void {
    let state: ShoppingState;
    try {
      state = Store.load();
    } catch (error) {
      Toast.error(error);
      state = Store.empty();
    }
    const items = ShoppingList.items(state);
    const checked = new Set(state.checked);
    const open = items.filter((i) => !checked.has(i.key));
    const done = items.filter((i) => checked.has(i.key));

    ShoppingList.q("[data-items]").replaceChildren(
      ...AISLE_ORDER.flatMap((aisle) => {
        const group = open.filter((i) => i.aisle === aisle);
        if (group.length === 0) {
          return [];
        }
        const heading = document.createElement("h3");
        heading.className = "aisle";
        heading.textContent = aisle;
        const list = document.createElement("ul");
        list.className = "items";
        list.append(...group.map((i) => ShoppingList.renderItem(i, false)));
        return [heading, list];
      }),
    );
    ShoppingList.q("[data-done]").replaceChildren(...done.map((i) => ShoppingList.renderItem(i, true)));
    ShoppingList.q("[data-done-wrap]").hidden = done.length === 0;
    ShoppingList.q("[data-done-count]").textContent = `(${done.length})`;
    ShoppingList.q("[data-open-count]").textContent = open.length ? String(open.length) : "";
    ShoppingList.q("[data-empty]").hidden = items.length > 0;
    ShoppingList.q<HTMLButtonElement>("[data-share]").disabled = open.length === 0;
    ShoppingList.q<HTMLButtonElement>("[data-clear]").disabled = items.length === 0;

    ShoppingList.q("[data-selected]").replaceChildren(
      ...Object.entries(state.recipes)
        .filter(([ref]) => ShoppingList.recipes.has(ref))
        .map(([ref, factor]) => ShoppingList.renderSelected(ref, factor)),
    );

    for (const li of ShoppingList.q("[data-picker]").querySelectorAll<HTMLLIElement>("li")) {
      const pressed = state.recipes[li.dataset.ref ?? ""] !== undefined;
      li.querySelector("[data-pick]")?.setAttribute("aria-pressed", String(pressed));
    }
  }

  private static icon(name: string): SVGSVGElement {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icon");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#i-${name}`);
    svg.append(use);
    return svg;
  }

  private static button(action: string, icon: string, label: string, data: Record<string, string>): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.action = action;
    Object.assign(button.dataset, data);
    button.setAttribute("aria-label", label);
    button.append(ShoppingList.icon(icon));
    return button;
  }

  private static renderSelected(ref: string, factor: number): HTMLLIElement {
    const recipe = ShoppingList.recipes.get(ref);
    if (!recipe) {
      throw new Error(`Unbekanntes Rezept ${ref}`);
    }
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = recipe.url;
    link.textContent = recipe.title;
    const value = document.createElement("span");
    value.className = "factor";
    value.textContent = Quantity.formatFactor(factor);
    value.title = recipe.yield ? Quantity.scaleText(recipe.yield, factor) : "";
    li.append(
      link,
      ShoppingList.button("less", "minus", `${recipe.title}: weniger`, { ref }),
      value,
      ShoppingList.button("more", "plus", `${recipe.title}: mehr`, { ref }),
      ShoppingList.button("remove-recipe", "x", `${recipe.title} entfernen`, { ref }),
    );
    return li;
  }

  private static renderItem(item: Item, done: boolean): HTMLLIElement {
    const li = document.createElement("li");
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = done;
    box.dataset.key = item.key;

    const text = document.createElement("span");
    text.className = "item__text";
    const name = document.createElement("span");
    name.className = "item__name";
    const amount = ShoppingList.amountText(item);
    if (amount) {
      const strong = document.createElement("span");
      strong.className = "item__amount";
      strong.textContent = amount;
      name.append(strong);
    }
    name.append(item.name);
    const sources = document.createElement("span");
    sources.className = "item__sources";
    sources.textContent = [...item.sources].join(" · ");
    text.append(name, sources);

    label.append(box, text);
    li.append(label);
    if (item.extraId) {
      const remove = ShoppingList.button("remove-extra", "x", `${item.name} entfernen`, { id: item.extraId });
      remove.className = "item__remove";
      li.append(remove);
    }
    return li;
  }
}
