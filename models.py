from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Common Models
class TextContent(BaseModel):
    type: str = "text"
    text: str

class ToolResponse(BaseModel):
    content: List[TextContent]

# Recipe MCP Server Models
class GetRecipeInput(BaseModel):
    dish_name: str

class GetRecipeOutput(BaseModel):
    required_ingredients: List[str]
    recipe_steps: List[str]

# Delivery MCP Server Models
class CompareIngredientsInput(BaseModel):
    required: List[str]
    available: List[str]

class CompareIngredientsOutput(BaseModel):
    missing_ingredients: List[str]

class PlaceOrderInput(BaseModel):
    items: List[str]

class PlaceOrderOutput(BaseModel):
    order_id: str
    total: float
    order_placed: bool

class GetOrderStatusInput(BaseModel):
    order_id: str

class GetOrderStatusOutput(BaseModel):
    order_id: str
    status: str
    items: List[str]
    total: float

# Gmail MCP Server Models
class SendEmailInput(BaseModel):
    to: str
    subject: str
    message: str

class SendEmailOutput(BaseModel):
    message_id: Optional[str]
    email_sent: bool 