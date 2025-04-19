from mcp.server import FastMCP
from mcp.types import TextContent
from typing import Dict, List, Any
from models import (
    GetRecipeInput, GetRecipeOutput,
    ErrorResponse,
    GetPantryInput, GetPantryOutput,
    PantryCheckInput, PantryCheckOutput
)
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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
    },
    "beef stir fry": {
        "ingredients": [
            "beef sirloin",
            "broccoli",
            "carrots",
            "bell peppers",
            "soy sauce",
            "garlic",
            "ginger",
            "vegetable oil",
            "cornstarch",
            "rice"
        ],
        "steps": [
            "Slice beef into thin strips",
            "Cut vegetables into bite-sized pieces",
            "Mix soy sauce and cornstarch for sauce",
            "Heat oil in a wok or large pan",
            "Stir-fry beef until browned",
            "Remove beef and set aside",
            "Stir-fry vegetables until crisp-tender",
            "Add back beef and sauce",
            "Cook until sauce thickens",
            "Serve over rice"
        ]
    },
    "mushroom risotto": {
        "ingredients": [
            "arborio rice",
            "mushrooms",
            "onion",
            "garlic",
            "white wine",
            "vegetable broth",
            "parmesan cheese",
            "butter",
            "olive oil",
            "thyme"
        ],
        "steps": [
            "Sauté mushrooms in butter until golden",
            "Remove mushrooms and set aside",
            "Sauté onion and garlic in olive oil",
            "Add rice and toast for 2 minutes",
            "Add wine and stir until absorbed",
            "Add hot broth gradually, stirring constantly",
            "Cook until rice is creamy and al dente",
            "Stir in mushrooms and parmesan",
            "Season with thyme and serve hot"
        ]
    },
    "fish tacos": {
        "ingredients": [
            "white fish fillets",
            "lime",
            "tortillas",
            "cabbage",
            "cilantro",
            "sour cream",
            "avocado",
            "chili powder",
            "cumin",
            "garlic powder"
        ],
        "steps": [
            "Season fish with spices",
            "Cook fish until flaky",
            "Warm tortillas",
            "Shred cabbage and chop cilantro",
            "Slice avocado",
            "Mix sour cream with lime juice",
            "Assemble tacos with fish and toppings",
            "Serve with lime wedges"
        ]
    },
    "vegetable lasagna": {
        "ingredients": [
            "lasagna noodles",
            "zucchini",
            "spinach",
            "ricotta cheese",
            "mozzarella cheese",
            "marinara sauce",
            "garlic",
            "onion",
            "basil",
            "olive oil"
        ],
        "steps": [
            "Cook lasagna noodles",
            "Sauté zucchini, garlic, and onion",
            "Wilt spinach",
            "Mix ricotta with basil",
            "Layer: sauce, noodles, vegetables, cheese",
            "Repeat layers",
            "Top with mozzarella",
            "Bake until bubbly and golden",
            "Let rest before serving"
        ]
    },
    "chicken fajitas": {
        "ingredients": [
            "chicken breast",
            "bell peppers",
            "onion",
            "tortillas",
            "lime",
            "cumin",
            "chili powder",
            "garlic",
            "olive oil",
            "sour cream"
        ],
        "steps": [
            "Slice chicken and vegetables",
            "Season chicken with spices",
            "Heat oil in a large skillet",
            "Cook chicken until done",
            "Sauté peppers and onions",
            "Warm tortillas",
            "Serve with lime and sour cream",
            "Let everyone assemble their own fajitas"
        ]
    },
    "shrimp scampi": {
        "ingredients": [
            "shrimp",
            "linguine",
            "garlic",
            "white wine",
            "lemon",
            "butter",
            "olive oil",
            "parsley",
            "red pepper flakes",
            "salt"
        ],
        "steps": [
            "Cook linguine according to package",
            "Sauté garlic in olive oil and butter",
            "Add shrimp and cook until pink",
            "Add wine and lemon juice",
            "Simmer until sauce reduces",
            "Toss with pasta",
            "Add parsley and red pepper flakes",
            "Serve immediately"
        ]
    },
    "thai green curry": {
        "ingredients": [
            "green curry paste",
            "coconut milk",
            "chicken thighs",
            "bamboo shoots",
            "bell peppers",
            "fish sauce",
            "palm sugar",
            "thai basil",
            "lime leaves",
            "rice"
        ],
        "steps": [
            "Cook curry paste in coconut milk",
            "Add chicken and simmer",
            "Add vegetables",
            "Season with fish sauce and palm sugar",
            "Add lime leaves",
            "Cook until chicken is done",
            "Stir in thai basil",
            "Serve over rice"
        ]
    },
    "beef bourguignon": {
        "ingredients": [
            "beef chuck",
            "bacon",
            "red wine",
            "pearl onions",
            "mushrooms",
            "carrots",
            "beef broth",
            "thyme",
            "bay leaves",
            "butter"
        ],
        "steps": [
            "Brown bacon and set aside",
            "Brown beef in batches",
            "Sauté vegetables",
            "Add wine and reduce",
            "Add broth and herbs",
            "Simmer until beef is tender",
            "Add mushrooms and pearl onions",
            "Cook until vegetables are tender",
            "Serve with crusty bread"
        ]
    },
    "eggplant parmesan": {
        "ingredients": [
            "eggplant",
            "breadcrumbs",
            "eggs",
            "mozzarella cheese",
            "parmesan cheese",
            "marinara sauce",
            "basil",
            "olive oil",
            "garlic",
            "salt"
        ],
        "steps": [
            "Slice and salt eggplant",
            "Dip in egg then breadcrumbs",
            "Fry until golden brown",
            "Layer: sauce, eggplant, cheese",
            "Repeat layers",
            "Top with remaining cheese",
            "Bake until bubbly",
            "Garnish with fresh basil"
        ]
    },
    "lemon herb salmon": {
        "ingredients": [
            "salmon fillets",
            "lemon",
            "garlic",
            "dill",
            "parsley",
            "olive oil",
            "butter",
            "capers",
            "salt",
            "pepper"
        ],
        "steps": [
            "Preheat oven to 400°F",
            "Mix herbs, garlic, and oil",
            "Season salmon with salt and pepper",
            "Spread herb mixture on salmon",
            "Add lemon slices and capers",
            "Bake until salmon flakes easily",
            "Drizzle with melted butter",
            "Serve with extra lemon"
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

# @mcp.tool()
# def compare_ingredients(input: CompareIngredientsInput) -> dict:
#     """Compare required ingredients against available ones and return missing ingredients"""
#     try:
#         # Convert both lists to lowercase for case-insensitive comparison
#         required = set(item.lower() for item in input.required)
#         available = set(item.lower() for item in input.available)
        
#         # Find missing ingredients (using set difference)
#         missing = list(required - available)
        
#         # Sort the list for consistent output
#         missing.sort()
        
#         # Create and validate output model
#         output = CompareIngredientsOutput(missing_ingredients=missing)
        
#         # Return in MCP format
#         return {
#             "content": [
#                 {
#                     "type": "text",
#                     "text": output.model_dump_json()
#                 }
#             ]
#         }
#     except Exception as e:
#         error = ErrorResponse(
#             error_type="ComparisonError",
#             message=f"Failed to compare ingredients: {str(e)}",
#             details={
#                 "required": input.required,
#                 "available": input.available
#             }
#         )
#         return {
#             "content": [
#                 {
#                     "type": "text",
#                     "text": error.model_dump_json()
#                 }
#             ]
#         }

# @mcp.tool()
# async def get_pantry_items(input: GetPantryInput) -> dict:
#     """Get user's available ingredients based on recipe requirements"""
#     try:
#         required_ingredients = input.required_ingredients

#         print("\nFor this recipe, you'll need:")
#         for i, ingredient in enumerate(required_ingredients, 1):
#             print(f"{i}. {ingredient}")

#         print("\nEnter the numbers of ingredients you ALREADY HAVE (separated by spaces):")
#         while True:
#             try:
#                 available_nums = input().strip().split()
#                 available_nums = [int(num) for num in available_nums if 1 <= int(num) <= len(required_ingredients)]
#                 available_ingredients = [required_ingredients[i-1] for i in available_nums]
                
#                 # Create and validate output
#                 output = GetPantryOutput(available_ingredients=available_ingredients)
                
#                 return {
#                     "content": [
#                         {
#                             "type": "text",
#                             "text": output.model_dump_json()
#                         }
#                     ]
#                 }
#             except ValueError:
#                 print("Please enter valid numbers separated by spaces. Try again:")

#     except Exception as e:
#         error = ErrorResponse(
#             error_type="PantryError",
#             message=f"Error getting pantry items: {str(e)}",
#             details={"required_ingredients": required_ingredients}
#         )
#         return {
#             "content": [
#                 {
#                     "type": "text",
#                     "text": error.model_dump_json()
#                 }
#             ]
#         }

@mcp.tool()
def check_pantry(input: PantryCheckInput) -> Dict[str, Any]:
    """Check what ingredients are available in user's pantry and what's missing from required ingredients so that you may place an order for the missing items."""
    logger.info(f"Checking pantry for required ingredients: {input.required_ingredients}")
    
    # Get pantry items from user input
    print("\nPlease enter the ingredients you have in your pantry.")
    print("Enter each ingredient on a new line. Type 'done' when finished.")
    print("\nRequired ingredients:")
    for ing in input.required_ingredients:
        print(f"- {ing}")
    
    pantry_items = []
    while True:
        try:
            item = input().strip().lower()
            if item == 'done':
                break
            if item:  # Only add non-empty items
                pantry_items.append(item)
        except EOFError:
            break
    
    # Compare ingredients to find missing ones
    missing_ingredients = []
    available_ingredients = []
    
    for required in input.required_ingredients:
        # Check if any pantry item matches or is similar to the required ingredient
        found = False
        for pantry_item in pantry_items:
            # Simple matching - could be enhanced with fuzzy matching
            if required.lower() in pantry_item or pantry_item in required.lower():
                available_ingredients.append(required)
                found = True
                break
        if not found:
            missing_ingredients.append(required)
    
    # Create message
    if missing_ingredients:
        message = f"You have {len(available_ingredients)} of {len(input.required_ingredients)} required ingredients.\n"
        message += "Missing ingredients:\n" + "\n".join(f"- {ing}" for ing in missing_ingredients)
    else:
        message = "You have all required ingredients!"
    
    result = PantryCheckOutput(
        available_ingredients=available_ingredients,
        missing_ingredients=missing_ingredients,
        message=message
    )
    
    return {
        "content": [{
            "text": result.model_dump_json()
        }]
    }

def main():
    print("Recipe MCP server running...")
    mcp.run()

if __name__ == "__main__":
    main() 