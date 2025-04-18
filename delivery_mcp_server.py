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