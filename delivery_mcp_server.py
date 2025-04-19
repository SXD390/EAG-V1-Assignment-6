from mcp.server import FastMCP
from mcp.types import TextContent
from typing import Dict
import uuid
import time
from models import (
    PlaceOrderInput, PlaceOrderOutput,
    GetOrderStatusInput, GetOrderStatusOutput,
    ErrorResponse
)

# Initialize the MCP server
mcp = FastMCP("Delivery")

# Simulated product database
PRODUCTS = {
    # Original recipe ingredients
    "spaghetti": 2.99,
    "eggs": 3.49,
    "pecorino cheese": 6.99,
    "guanciale": 8.99,
    "black pepper": 3.99,
    "salt": 1.99,
    "chicken breast": 7.99,
    "onion": 0.99,
    "garlic": 1.49,
    "ginger": 2.49,
    "curry powder": 4.99,
    "coconut milk": 2.99,
    "tomatoes": 2.49,
    "rice": 3.99,
    
    # Beef Stir Fry ingredients
    "beef sirloin": 12.99,
    "broccoli": 2.99,
    "carrots": 1.99,
    "bell peppers": 2.49,
    "soy sauce": 3.49,
    "vegetable oil": 2.99,
    "cornstarch": 1.99,
    
    # Mushroom Risotto ingredients
    "arborio rice": 4.99,
    "mushrooms": 3.99,
    "white wine": 8.99,
    "vegetable broth": 2.99,
    "parmesan cheese": 6.99,
    "butter": 3.99,
    "olive oil": 4.99,
    "thyme": 1.99,
    
    # Fish Tacos ingredients
    "white fish fillets": 9.99,
    "lime": 0.99,
    "tortillas": 2.99,
    "cabbage": 2.49,
    "cilantro": 1.49,
    "sour cream": 2.99,
    "avocado": 2.99,
    "chili powder": 3.49,
    "cumin": 3.49,
    "garlic powder": 2.99,
    
    # Vegetable Lasagna ingredients
    "lasagna noodles": 3.99,
    "zucchini": 1.99,
    "spinach": 2.99,
    "ricotta cheese": 4.99,
    "mozzarella cheese": 4.99,
    "marinara sauce": 3.99,
    "basil": 1.99,
    
    # Chicken Fajitas ingredients (some already listed)
    
    # Shrimp Scampi ingredients
    "shrimp": 12.99,
    "linguine": 2.99,
    "lemon": 0.99,
    "parsley": 1.49,
    "red pepper flakes": 2.49,
    
    # Thai Green Curry ingredients
    "green curry paste": 3.99,
    "chicken thighs": 6.99,
    "bamboo shoots": 2.49,
    "fish sauce": 2.99,
    "palm sugar": 3.49,
    "thai basil": 1.99,
    "lime leaves": 2.49,
    
    # Beef Bourguignon ingredients
    "beef chuck": 10.99,
    "bacon": 5.99,
    "red wine": 12.99,
    "pearl onions": 2.99,
    "bay leaves": 1.99,
    
    # Eggplant Parmesan ingredients
    "eggplant": 2.99,
    "breadcrumbs": 1.99,
    
    # Lemon Herb Salmon ingredients
    "salmon fillets": 14.99,
    "dill": 1.99,
    "capers": 3.49,
    "pepper": 3.99,

    # Masala Dosa ingredients
    "dosa batter": 2.99,
    "potatoes": 1.99,
    "onions": 0.99,
    "mustard seeds": 0.49,
    "urad dal": 1.49
    
}

# Simulated orders database
ORDERS = {}

@mcp.tool()
def place_order(input: PlaceOrderInput) -> dict:
    """Place an order for missing ingredients"""
    try:
        items = [item.lower() for item in input.items]
        
        # Validate all items exist in product database
        invalid_items = [item for item in items if item not in PRODUCTS]
        if invalid_items:
            raise ValueError(f"Invalid items: {', '.join(invalid_items)}")
        
        # Calculate total price
        total = sum(PRODUCTS.get(item, 0) for item in items)
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        # Store order
        ORDERS[order_id] = {
            "items": items,
            "total": total,
            "status": "placed",
            "timestamp": time.time()
        }
        
        # Create and validate output model
        output = PlaceOrderOutput(
            order_id=order_id,
            total=total,
            order_placed=True
        )
        
        # Return in MCP format
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
            error_type="OrderError",
            message=f"Failed to place order: {str(e)}",
            details={
                "items": input.items,
                "valid_products": list(PRODUCTS.keys())
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

@mcp.tool()
def get_order_status(input: GetOrderStatusInput) -> dict:
    """Get the status of an order"""
    try:
        if input.order_id not in ORDERS:
            raise ValueError(f"Order {input.order_id} not found")
        
        order = ORDERS[input.order_id]
        
        # Simulate order progress based on time
        elapsed = time.time() - order["timestamp"]
        if elapsed < 60:  # 1 minute
            status = "processing"
        elif elapsed < 120:  # 2 minutes
            status = "out for delivery"
        else:
            status = "delivered"
        
        order["status"] = status
        
        # Create and validate output model
        output = GetOrderStatusOutput(
            order_id=input.order_id,
            status=status,
            items=order["items"],
            total=order["total"]
        )
        
        # Return in MCP format
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
            error_type="StatusError",
            message=f"Failed to get order status: {str(e)}",
            details={
                "order_id": input.order_id,
                "exists": input.order_id in ORDERS
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
    print("Delivery MCP server running...")
    main() 