export interface Extra {
  id: string;
  text: string;
}

export interface ShoppingState {
  v: 1;
  recipes: Record<string, number>;
  checked: string[];
  extras: Extra[];
}

const KEY = "gute-sachen:einkaufsliste";
const EVENT = "shopping-change";

export class Store {
  public static empty(): ShoppingState {
    return { v: 1, recipes: {}, checked: [], extras: [] };
  }

  public static load(): ShoppingState {
    let raw: string | null;
    try {
      raw = localStorage.getItem(KEY);
    } catch {
      return Store.empty();
    }
    if (raw === null) {
      return Store.empty();
    }
    const state: unknown = JSON.parse(raw);
    if (!Store.isValid(state)) {
      Store.save(Store.empty());
      throw new Error("Die gespeicherte Einkaufsliste war beschädigt und wurde zurückgesetzt.");
    }
    return state;
  }

  public static save(state: ShoppingState): void {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      throw new Error("Die Einkaufsliste konnte in diesem Browser nicht gespeichert werden.");
    }
    document.dispatchEvent(new CustomEvent(EVENT));
  }

  public static update(change: (state: ShoppingState) => void): ShoppingState {
    const state = Store.load();
    change(state);
    Store.save(state);
    return state;
  }

  public static count(state: ShoppingState): number {
    return Object.keys(state.recipes).length + state.extras.length;
  }

  public static onChange(listener: () => void): void {
    document.addEventListener(EVENT, listener);
    window.addEventListener("storage", (e) => {
      if (e.key === KEY) {
        listener();
      }
    });
  }

  private static isValid(value: unknown): value is ShoppingState {
    if (typeof value !== "object" || value === null) {
      return false;
    }
    const s = value as Record<string, unknown>;
    const recipes = s.recipes as Record<string, unknown>;
    return (
      s.v === 1 &&
      typeof recipes === "object" &&
      recipes !== null &&
      Object.values(recipes).every((f) => typeof f === "number" && f > 0) &&
      Array.isArray(s.checked) &&
      s.checked.every((c) => typeof c === "string") &&
      Array.isArray(s.extras) &&
      s.extras.every(
        (e) =>
          typeof e === "object" &&
          e !== null &&
          typeof (e as Extra).id === "string" &&
          typeof (e as Extra).text === "string",
      )
    );
  }
}
