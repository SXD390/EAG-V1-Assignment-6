from mcp.server import FastMCP
from mcp.types import TextContent
from typing import Dict
from models import GetRecipeInput, GetRecipeOutput, ErrorResponse

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
def get_recipe(input: GetRecipeInput) -> dict:
    """Get recipe and ingredients for a dish"""
    try:
        dish_name = input.dish_name.lower()
        
        if dish_name not in RECIPES:
            error = ErrorResponse(
                error_type="RecipeNotFound",
                message=f"Recipe for '{dish_name}' not found",
                details={
                    "requested_recipe": dish_name,
                    "available_recipes": list(RECIPES.keys())
                }
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": error.model_dump_json()
                    }
                ]
            }
        
        recipe = RECIPES[dish_name]
        
        # Create and validate output model
        output = GetRecipeOutput(
            required_ingredients=recipe["ingredients"],
            recipe_steps=recipe["steps"]
        )
        
        # Return in MCP format with model data
        return {
            "content": [
                {
                    "type": "text",
                    "text": output.model_dump_json()
                }
            ]
        }
    except Exception as e:
        error = ErrorResponse(
            error_type="RecipeError",
            message=f"Failed to get recipe: {str(e)}",
            details={
                "dish_name": input.dish_name if hasattr(input, 'dish_name') else None,
                "error": str(e)
            }
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": error.model_dump_json()
                }
            ]
        }

def main():
    mcp.run()

if __name__ == "__main__":
    print("Recipe MCP server running...")
    main() 