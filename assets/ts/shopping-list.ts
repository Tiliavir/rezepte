type Splitted = { amount: number, unit: string, name: string };
type Aggregated = { [ingredient: string]: { [unit: string]: number } };

export class ShoppingList {
  private static prep(ingredients: string[]): Aggregated {
    const regex = /^([\d\/.,]+)?\s*(?:(EL|TL|ml|dl|l|g|kg|cm|Prise|Dose|Bund|Pck.)\s+)?(.+)$/;
    let splitted: Splitted[] = [];
    for (let ingredient of ingredients) {
      let matches = ingredient.match(regex);
      splitted.push({amount: +matches[1], unit: matches[2] || "count", name: matches[3]});
    }
    const ingredientsGrouped: Aggregated = {};
    for (let value of splitted) {
      if (!ingredientsGrouped[value.name]) {
        ingredientsGrouped[value.name] = {};
      }
      if (value.amount) {
        if (!ingredientsGrouped[value.name][value.unit]) {
          ingredientsGrouped[value.name][value.unit] = value.amount;
        } else {
          ingredientsGrouped[value.name][value.unit] += value.amount;
        }
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

  private static getFormattedIngredientStrings(ingredientsByUnitsAndAmount: Aggregated): string[] {
    let ingrFormatted: string[] = [];
    for (let ingredient in ingredientsByUnitsAndAmount) {
      let amounts = "";
      for (let unit in ingredientsByUnitsAndAmount[ingredient]) {
        let amount = ingredientsByUnitsAndAmount[ingredient][unit];
        if (amount) {
          // add separator if not first amount
          amounts += amounts !== "" ? ", " : "";
          amounts += amount + "" + (unit == "count" ? "" : unit);
        }
      }
      ingrFormatted.push(ingredient + (amounts ? ": " + amounts : ""));
    }
    return ingrFormatted.sort();
  }
}

document.addEventListener("DOMContentLoaded", function () {
  ShoppingList.ready();
});
