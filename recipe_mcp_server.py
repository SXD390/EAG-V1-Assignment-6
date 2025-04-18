from mcp.server import FastMCP
from mcp.types import TextContent
from typing import Dict
from models import GetRecipeInput, GetRecipeOutput

# Initialize the MCP server
mcp = FastMCP("Recipe")

# Simulated recipe database
RECIPES = {
    "pasta carbonara": {
        "ingredients": [
            "spaghetti",
            "eggs",
            "pecorino cheese",
            "guanciale",
            "black pepper",
            "salt"
        ],
        "steps": [
            "Bring a large pot of salted water to boil",
            "Cook spaghetti according to package instructions",
            "While pasta cooks, whisk eggs and grated pecorino in a bowl",
            "Crisp guanciale in a pan until golden brown",
            "Drain pasta, reserving some pasta water",
            "Mix pasta with egg mixture and guanciale",
            "Add pasta water if needed to create a creamy sauce",
            "Season with black pepper and serve immediately"
        ]
    },
    "chicken curry": {
        "ingredients": [
            "chicken breast",
            "onion",
            "garlic",
            "ginger",
            "curry powder",
            "coconut milk",
            "tomatoes",
            "rice"
        ],
        "steps": [
            "Cut chicken into bite-sized pieces",
            "Dice onion, mince garlic and ginger",
            "Sauté onion until translucent",
            "Add garlic and ginger, cook until fragrant",
            "Add curry powder and stir",
            "Add chicken and cook until browned",
            "Pour in coconut milk and diced tomatoes",
            "Simmer for 20 minutes",
            "Serve over cooked rice"
        ]
    }
}

@mcp.tool()
def get_recipe(input: GetRecipeInput) -> Dict:
    """Get recipe and ingredients for a dish"""
    dish_name = input.dish_name.lower()
    
    if dish_name not in RECIPES:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Recipe for '{dish_name}' not found"
                )
            ]
        }
    
    recipe = RECIPES[dish_name]
    output = GetRecipeOutput(
        required_ingredients=recipe["ingredients"],
        recipe_steps=recipe["steps"]
    )
    
    # Format the recipe as a human-readable string
    recipe_text = "Recipe found!\n\n"
    recipe_text += "Required ingredients:\n"
    recipe_text += "\n".join(f"- {ing}" for ing in output.required_ingredients)
    recipe_text += "\n\nSteps:\n"
    recipe_text += "\n".join(f"{i+1}. {step}" for i, step in enumerate(output.recipe_steps))
    
    return {
        "content": [
            TextContent(
                type="text",
                text=recipe_text
            )
        ]
    }

def main():
    mcp.run()

if __name__ == "__main__":
    print("Recipe MCP server running...")
    main() 