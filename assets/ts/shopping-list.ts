type Splitted = { amount: number, unit: string, name: string };
type Aggregated = { [ingredient: string]: { [unit: string]: number } };

const UNITS = ['EL', 'TL', 'ml', 'dl', 'l', 'g', 'kg', 'cm', 'Prise', 'Dose', 'Bund', 'Pck\\.'];
const INGREDIENT_REGEX = new RegExp(`^([\\d/.,]+)?\\s*(?:(${UNITS.join('|')})\\s+)?(.+)$`);

export class ShoppingList {
  private static prep(ingredients: string[]): Aggregated {
    let splitted: Splitted[] = [];
    for (let ingredient of ingredients) {
      let matches = INGREDIENT_REGEX.exec(ingredient);
      splitted.push({amount: +matches[1], unit: matches[2] || "count", name: matches[3]});
    }
    const ingredientsGrouped: Aggregated = {};
    for (let value of splitted) {
      ingredientsGrouped[value.name] ??= {};
      if (value.amount) {
        ingredientsGrouped[value.name][value.unit] = (ingredientsGrouped[value.name][value.unit] ?? 0) + value.amount;
      }
    }
    return ingredientsGrouped;
  }

  public static ready(): void {
    let shoppingList = document.querySelector(".shopping-list");
    let ingredients = shoppingList.querySelector(".ingredients");

    shoppingList.querySelectorAll("input")
      .forEach((el) => {
        el.addEventListener("click", function () {
          el.classList.toggle("active");

          let ingr: string[] = [];
          shoppingList.querySelectorAll("input:checked")
            .forEach((e) => {
              // @ts-ignore
              let ingredientsByRecipe: { [key: string]: string[] } = document.body["ingredients"];
              ingr.push(...ingredientsByRecipe[e.id]);
            });

          let ingredientsByUnitsAndAmount = ShoppingList.prep(ingr);
          ingredients.innerHTML = "<h3>Zutaten</h3><ul>";
          let sortedIngredients = ShoppingList.getFormattedIngredientStrings(ingredientsByUnitsAndAmount);
          for (let entry of sortedIngredients) {
            ingredients.innerHTML += "<li>" + entry + "</li>";
          }
          ingredients.innerHTML += "</ul>";
        })
      });
  }

  private static formatAmounts(units: { [unit: string]: number }): string {
    return Object.entries(units)
      .filter(([, amount]) => amount)
      .map(([unit, amount]) => amount + (unit === "count" ? "" : unit))
      .join(", ");
  }

  private static getFormattedIngredientStrings(ingredientsByUnitsAndAmount: Aggregated): string[] {
    let ingrFormatted: string[] = [];
    for (let ingredient in ingredientsByUnitsAndAmount) {
      const amounts = ShoppingList.formatAmounts(ingredientsByUnitsAndAmount[ingredient]);
      ingrFormatted.push(ingredient + (amounts ? ": " + amounts : ""));
    }
    return ingrFormatted.sort((a, b) => a.localeCompare(b));
  }
}

document.addEventListener("DOMContentLoaded", function () {
  ShoppingList.ready();
});
