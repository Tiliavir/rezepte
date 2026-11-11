// biome-ignore assist/source/organizeImports: keep lunr-languages in load order (stemmer support first)
import lunr from "lunr";
import stemmerSupport from "lunr-languages/lunr.stemmer.support";
import german from "lunr-languages/lunr.de";
import { Toast } from "./lib/toast";

stemmerSupport(lunr);
german(lunr);

interface SearchData {
  index: object;
}

class Search {
  private static index: lunr.Index | null = null;
  private static loading: Promise<void> | null = null;
  private static cards: HTMLLIElement[] = [];
  private static grid: HTMLElement;
  private static input: HTMLInputElement;
  private static category = "";
  private static indexUrl = "";

  public static initialize(): void {
    const form = document.querySelector<HTMLFormElement>("[data-search]");
    const grid = document.getElementById("rezepte");
    const input = form?.querySelector<HTMLInputElement>("input[type=search]");
    if (!form || !grid || !input) {
      return;
    }
    Search.grid = grid;
    Search.input = input;
    Search.indexUrl = form.dataset.index ?? "";
    Search.cards = [...grid.querySelectorAll<HTMLLIElement>(":scope > li")];

    form.addEventListener("submit", (e) => e.preventDefault());
    input.addEventListener("input", () => Search.update());
    input.addEventListener("focus", () => Search.load(), { once: true });
    document.addEventListener("keydown", (e) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (e.key === "/" && !typing) {
        e.preventDefault();
        input.focus();
      } else if (e.key === "Escape" && e.target === input) {
        input.value = "";
        Search.update();
      }
    });

    for (const chip of document.querySelectorAll<HTMLAnchorElement>("[data-filter]")) {
      chip.addEventListener("click", (e) => {
        e.preventDefault();
        Search.category = chip.dataset.filter ?? "";
        for (const other of document.querySelectorAll("[data-filter]")) {
          other.setAttribute("aria-current", String(other === chip));
        }
        Search.update();
      });
    }

    const params = new URLSearchParams(window.location.search);
    const query = params.get("q");
    if (query) {
      input.value = query;
      Search.update();
    }
  }

  private static load(): Promise<void> {
    Search.loading ??= fetch(Search.indexUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Suchindex konnte nicht geladen werden (${response.status}).`);
        }
        return response.json() as Promise<SearchData>;
      })
      .then((data) => {
        Search.index = lunr.Index.load(data.index);
      });
    return Search.loading;
  }

  private static query(text: string): string[] {
    if (!Search.index) {
      return [];
    }
    const tokens = lunr
      .tokenizer(text)
      .map((token) => lunr.de.trimmer(token))
      .filter((token): token is lunr.Token => token !== undefined && token.toString().length > 0);
    if (tokens.length === 0) {
      return [];
    }
    return Search.index
      .query((q) => {
        for (const token of tokens) {
          const term = token.toString();
          q.term(term, { boost: 10, presence: lunr.Query.presence.OPTIONAL });
          q.term(term, { usePipeline: false, wildcard: lunr.Query.wildcard.TRAILING, boost: 3 });
          const stem = String(lunr.de.stemmer(token.clone()) ?? "");
          if (stem.length >= 3) {
            q.term(stem, {
              usePipeline: false,
              wildcard: lunr.Query.wildcard.LEADING | lunr.Query.wildcard.TRAILING,
              boost: 1,
            });
          }
        }
      })
      .map((result) => decodeURI(result.ref));
  }

  private static update(): void {
    const text = Search.input.value.trim();
    Search.syncUrl(text);
    if (text && !Search.index) {
      Search.load()
        .then(() => Search.update())
        .catch(Toast.error);
      return;
    }
    const visible = Search.matches(text);
    const shown = new Set(visible);
    for (const card of Search.cards) {
      card.hidden = !shown.has(card);
    }
    Search.grid.append(...visible, ...Search.cards.filter((c) => !shown.has(c)));
    Search.renderLabel(text, visible.length);
  }

  private static syncUrl(text: string): void {
    const url = new URL(window.location.href);
    if (text) {
      url.searchParams.set("q", text);
    } else {
      url.searchParams.delete("q");
    }
    window.history.replaceState(null, "", url);
  }

  private static matches(text: string): HTMLLIElement[] {
    const inCategory = (card: HTMLLIElement): boolean => !Search.category || card.dataset.category === Search.category;
    if (!text) {
      return Search.cards.filter(inCategory);
    }
    const byRef = new Map(Search.cards.map((c) => [decodeURI(c.dataset.ref ?? ""), c]));
    return Search.query(text)
      .map((ref) => byRef.get(ref))
      .filter((c): c is HTMLLIElement => c !== undefined && inCategory(c));
  }

  private static renderLabel(text: string, count: number): void {
    const label = document.querySelector<HTMLElement>("[data-result-label]");
    if (label) {
      const chip = document.querySelector<HTMLElement>(`[data-filter="${CSS.escape(Search.category)}"]`);
      const scope = Search.category ? (chip?.firstChild?.textContent?.trim() ?? "") : "";
      const where = scope ? ` in ${scope}` : "";
      label.textContent = text ? `${count} Treffer für „${text}“${where}` : scope || "Alle Rezepte";
    }
    const empty = document.querySelector<HTMLElement>("[data-empty]");
    if (empty) {
      empty.hidden = count > 0;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => Search.initialize());
