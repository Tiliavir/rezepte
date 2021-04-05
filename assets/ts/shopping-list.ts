type Splitted = { amount: number, unit: string, name: string };
type Aggregated = { [ingredient: string]: { [unit: string]: number } };

export class ShoppingList {
  private static prep(ingredients: string[]): Aggregated {
    const regex = /^([\d\/.,]+)?\s*(?:(EL|TL|ml|dl|l|g|kg|Prise|Bund)\s+)?(.+)$/;
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

          let ingrFormatted: string[] = [];
          let ingredientsByUnitsAndAmount = ShoppingList.prep(ingr);
          for (let ingredient in ingredientsByUnitsAndAmount) {
            let amounts = "";
            for (let unit in ingredientsByUnitsAndAmount[ingredient]) {
              let amount = ingredientsByUnitsAndAmount[ingredient][unit];
              if (amount) {
                amounts += amount + "" + (unit == "count" ? "" : unit);
              }
            }
            ingrFormatted.push(ingredient + (amounts ? ": " + amounts : ""));
          }

          ingredients.innerHTML = "<h3>Zutaten</h3><ul>";
          for (let entry of ingrFormatted.sort()) {
            ingredients.innerHTML += "<li>" + entry + "</li>";
          }
          ingredients.innerHTML += "</ul>";
        })
      });
  }
}

document.addEventListener("DOMContentLoaded", function () {
  ShoppingList.ready();
});
