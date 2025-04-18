from typing import List, Dict, Any, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, constr

# Tool Response Models
class TextContent(BaseModel):
    """Model for text content in tool responses"""
    type: str = "text"
    text: str

class ToolResponse(BaseModel):
    """Model for tool responses"""
    content: List[TextContent]

# Input/Output Models for MCP Tools
class GetRecipeInput(BaseModel):
    """Input model for get_recipe tool"""
    dish_name: str

class GetRecipeOutput(BaseModel):
    """Output model for get_recipe tool"""
    required_ingredients: List[str]
    recipe_steps: List[str]

class CompareIngredientsInput(BaseModel):
    """Input model for compare_ingredients tool"""
    required: List[str]
    available: List[str]

class CompareIngredientsOutput(BaseModel):
    """Output model for compare_ingredients tool"""
    missing_ingredients: List[str]

class PlaceOrderInput(BaseModel):
    """Input model for place_order tool"""
    items: List[str]

class PlaceOrderOutput(BaseModel):
    """Output model for place_order tool"""
    order_placed: bool
    order_id: str
    total: float

class SendEmailInput(BaseModel):
    """Input model for send_email tool"""
    to: str
    subject: str
    message: str

class SendEmailOutput(BaseModel):
    """Output model for send_email tool"""
    message_id: str  # Only message_id is required for email confirmation

class GetOrderStatusInput(BaseModel):
    """Input model for get_order_status tool"""
    order_id: str

class GetOrderStatusOutput(BaseModel):
    """Output model for get_order_status tool"""
    order_id: str
    status: str
    items: List[str]
    total: float

# Perception Models
class RawUserInput(BaseModel):
    """Model for validating web form or user input"""
    dish_name: str | None = Field(
        None, 
        min_length=1, 
        max_length=100,
        description="Name of the dish to cook"
    )
    pantry_items: List[str] | None = Field(
        None,
        min_items=0,
        max_items=50,
        description="List of ingredients available in pantry"
    )
    user_email: EmailStr | None = Field(
        None,
        description="User's email for order notifications"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "dish_name": "pasta carbonara",
                "pantry_items": ["eggs", "cheese", "pepper"],
                "user_email": "user@example.com"
            }
        }

class UserIntent(BaseModel):
    """Model for parsed user intent"""
    dish_name: str = Field(min_length=1, max_length=100)
    pantry_items: List[str] = Field(default_factory=list)
    user_email: EmailStr

class PerceptionError(BaseModel):
    """Model for perception layer errors"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

# Memory Models
class AgentMemory(BaseModel):
    """Model for agent's memory state"""
    dish_name: constr(min_length=1, max_length=100) = ""
    pantry_items: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    required_ingredients: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    missing_ingredients: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    recipe_steps: List[str] = Field(default_factory=list)
    order_placed: bool = False
    order_id: Optional[str] = None
    email_sent: bool = False
    user_email: Optional[EmailStr] = None

class MemoryError(BaseModel):
    """Model for memory layer errors"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

# Decision Models
class ActionType(Enum):
    """Enum for different types of actions"""
    FETCH_RECIPE = "fetch_recipe"
    CHECK_INGREDIENTS = "check_ingredients"
    PLACE_ORDER = "place_order"
    SEND_EMAIL = "send_email"
    DISPLAY_RECIPE = "display_recipe"
    INVALID_INPUT = "invalid_input"

class FetchRecipeParams(BaseModel):
    """Parameters for fetch recipe action"""
    dish_name: str

class CheckIngredientsParams(BaseModel):
    """Parameters for check ingredients action"""
    required: List[str]
    available: List[str]

class PlaceOrderParams(BaseModel):
    """Parameters for place order action"""
    items: List[str]

class SendEmailParams(BaseModel):
    """Parameters for send email action"""
    email: str
    order_id: str
    items: List[str]

class DisplayRecipeParams(BaseModel):
    """Parameters for display recipe action"""
    steps: List[str]

class InvalidInputParams(BaseModel):
    """Parameters for invalid input action"""
    message: Optional[str] = None

# Union type for all action parameters
ActionParams = Union[
    FetchRecipeParams,
    CheckIngredientsParams,
    PlaceOrderParams,
    SendEmailParams,
    DisplayRecipeParams,
    InvalidInputParams
]

class Decision(BaseModel):
    """Model representing a decision about next action"""
    action: ActionType
    params: ActionParams
    reasoning: str
    fallback: Optional[str] = None

class ActionPlan(BaseModel):
    """Model representing the final action plan"""
    type: Literal["function_call"] = "function_call"
    function: str
    parameters: Dict[str, Dict[str, Any]]
    on_fail: str

class DecisionContext(BaseModel):
    """Model representing the input context for decision making"""
    current_state: Dict[str, Any]
    system_prompt: str

# Action Models
class EmailFormatParams(BaseModel):
    """Model for email formatting parameters"""
    items: List[str]
    order_id: str

class ErrorResponse(BaseModel):
    """Model for standardized error responses"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict) 