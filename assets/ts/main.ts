import { Store } from "./lib/store";
import { Toast } from "./lib/toast";
import { Recipe } from "./recipe";
import { ShoppingList } from "./shopping-list";

type Theme = "system" | "light" | "dark";

class App {
  public static initialize(): void {
    App.initTheme();
    App.initCartBadge();
    const recipe = document.querySelector<HTMLElement>("[data-recipe]");
    if (recipe) {
      Recipe.initialize(recipe);
    }
    const shopping = document.querySelector<HTMLElement>("[data-shopping]");
    if (shopping) {
      ShoppingList.initialize(shopping);
    }
  }

  private static initTheme(): void {
    const button = document.querySelector<HTMLButtonElement>("[data-theme-toggle]");
    const label = button?.querySelector<HTMLElement>("[data-theme-label]");
    if (!button || !label) {
      return;
    }
    const order: Theme[] = ["system", "light", "dark"];
    const names: Record<Theme, string> = { system: "wie System", light: "hell", dark: "dunkel" };
    const current = (): Theme => {
      const t = document.documentElement.dataset.theme;
      return t === "light" || t === "dark" ? t : "system";
    };
    const render = (): void => {
      const theme = current();
      label.textContent = `Farbschema: ${names[theme]}`;
      button.title = `Farbschema: ${names[theme]}`;
      button
        .querySelector("use")
        ?.setAttribute("href", theme === "light" ? "#i-sun" : theme === "dark" ? "#i-moon" : "#i-contrast");
    };
    button.addEventListener("click", () => {
      const next = order[(order.indexOf(current()) + 1) % order.length];
      if (next === "system") {
        delete document.documentElement.dataset.theme;
      } else {
        document.documentElement.dataset.theme = next;
      }
      try {
        if (next === "system") {
          localStorage.removeItem("theme");
        } else {
          localStorage.setItem("theme", next);
        }
      } catch {
        Toast.show("Farbschema gilt nur für diesen Besuch");
      }
      render();
    });
    button.hidden = false;
    render();
  }

  private static initCartBadge(): void {
    const badge = document.querySelector<HTMLElement>("[data-cart-count]");
    if (!badge) {
      return;
    }
    let last = -1;
    const render = (): void => {
      let count = 0;
      try {
        count = Store.count(Store.load());
      } catch (error) {
        Toast.error(error);
      }
      badge.textContent = String(count);
      badge.hidden = count === 0;
      if (last >= 0 && count > last) {
        badge.classList.remove("is-bumped");
        void badge.offsetWidth;
        badge.classList.add("is-bumped");
      }
      last = count;
    };
    Store.onChange(render);
    render();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    App.initialize();
  } catch (error) {
    Toast.error(error);
  }
});
