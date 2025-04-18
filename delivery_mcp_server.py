from mcp.server import FastMCP
from mcp.types import TextContent
from typing import Dict
import uuid
import time
from models import (
    CompareIngredientsInput, CompareIngredientsOutput,
    PlaceOrderInput, PlaceOrderOutput,
    GetOrderStatusInput, GetOrderStatusOutput
)

# Initialize the MCP server
mcp = FastMCP("Delivery")

# Simulated product database
PRODUCTS = {
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
    "rice": 3.99
}

# Simulated orders database
ORDERS = {}

@mcp.tool()
def compare_ingredients(input: CompareIngredientsInput) -> CompareIngredientsOutput:
    """Compare required ingredients against available ones and return missing ingredients"""
    # Convert both lists to lowercase for case-insensitive comparison
    required = set(item.lower() for item in input.required)
    available = set(item.lower() for item in input.available)
    
    # Find missing ingredients (using set difference)
    missing = list(required - available)
    
    # Sort the list for consistent output
    missing.sort()
    
    # Return output model directly
    return CompareIngredientsOutput(missing_ingredients=missing)

@mcp.tool()
def place_order(input: PlaceOrderInput) -> PlaceOrderOutput:
    """Place an order for missing ingredients"""
    items = [item.lower() for item in input.items]
    
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
    
    # Return output model directly
    return PlaceOrderOutput(
        order_id=order_id,
        total=total,
        order_placed=True
    )

@mcp.tool()
def get_order_status(input: GetOrderStatusInput) -> GetOrderStatusOutput:
    """Get the status of an order"""
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
    
    # Return output model directly
    return GetOrderStatusOutput(
        order_id=input.order_id,
        status=status,
        items=order["items"],
        total=order["total"]
    )

def main():
    mcp.run()
    

if __name__ == "__main__":
    print("Delivery MCP server running...")
    main() 