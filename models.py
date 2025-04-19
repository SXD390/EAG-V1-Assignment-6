from typing import List, Dict, Any, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, constr

# Action Type Enum
class ActionType(str, Enum):
    """Enum for different types of actions"""
    FETCH_RECIPE = "fetch_recipe"
    WAIT_FOR_RECIPE = "wait_for_recipe"
    GET_PANTRY = "get_pantry"
    PLACE_ORDER = "place_order"
    SEND_EMAIL = "send_email"
    DISPLAY_RECIPE = "display_recipe"
    CHECK_ORDER_STATUS = "check_order_status"
    INVALID_INPUT = "invalid_input"

# Tool Response Models
class TextContent(BaseModel):
    """Model for text content in tool responses"""
    type: str = "text"
    text: str

class ToolResponse(BaseModel):
    """Model for tool responses"""
    content: List[TextContent]

# Input/Output Models for MCP Tools
class RawInput(BaseModel):
    """Raw user input model"""
    raw_text: str = ""
    user_email: Optional[str] = None
    dish_name: Optional[str] = None

class UserIntent(BaseModel):
    """Enhanced user intent model"""
    dish_name: Optional[str] = None
    user_email: Optional[str] = None

class GetRecipeInput(BaseModel):
    """Input for get_recipe tool"""
    dish_name: str

class GetRecipeOutput(BaseModel):
    """Output from get_recipe tool"""
    recipe_name: Optional[str] = None
    required_ingredients: List[str]
    recipe_steps: List[str]

class PantryCheckInput(BaseModel):
    """Input for check_pantry tool"""
    ingredients: List[str]

class PantryCheckOutput(BaseModel):
    """Output from check_pantry tool"""
    available_ingredients: List[str]
    missing_ingredients: List[str]
    message: str

class PlaceOrderInput(BaseModel):
    """Input for place_order tool"""
    items: List[str]
    email: str

class PlaceOrderOutput(BaseModel):
    """Output from place_order tool"""
    order_id: str
    total: float
    order_placed: bool
    message: str

class SendEmailInput(BaseModel):
    """Input for send_email tool"""
    to_email: str
    subject: str
    body: str

class SendEmailOutput(BaseModel):
    """Output from send_email tool"""
    email_sent: bool
    message: str

class CheckOrderStatusParams(BaseModel):
    """Parameters for checking order status"""
    order_id: Optional[str] = None

class CheckOrderStatusOutput(BaseModel):
    """Output from check_order_status"""
    order_exists: bool
    order_id: Optional[str]
    message: str

class FetchRecipeParams(BaseModel):
    """Parameters for fetching recipe"""
    dish_name: str

class DisplayRecipeParams(BaseModel):
    """Parameters for displaying recipe"""
    steps: List[str]

class InvalidInputParams(BaseModel):
    """Parameters for invalid input"""
    message: str

class EmailFormatParams(BaseModel):
    """Parameters for formatting email"""
    items: List[str]
    order_id: str
    total: float

class ActionPlan(BaseModel):
    """Action plan from LLM"""
    type: str
    function: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    steps: Optional[List[str]] = None
    verify: Optional[str] = None
    next: Optional[str] = None
    fallback_plan: Optional[str] = None
    value: Optional[str] = None
    on_fail: Optional[str] = None

class Decision(BaseModel):
    """Decision made by decision layer"""
    action: ActionType
    params: Union[
        FetchRecipeParams,
        PantryCheckInput,
        PlaceOrderInput,
        SendEmailInput,
        CheckOrderStatusParams,
        DisplayRecipeParams,
        InvalidInputParams
    ]
    reasoning: str
    fallback: Optional[str] = None

# LLM Interaction Models
class ReasoningBlock(BaseModel):
    """Model for LLM reasoning steps"""
    type: Literal["reasoning_block"]
    reasoning_type: str
    steps: List[str]
    verify: str
    next: str
    fallback_plan: str

class FunctionCall(BaseModel):
    """Model for LLM function calls"""
    type: Literal["function_call"]
    function: str
    parameters: Dict[str, Any]
    on_fail: str

class FinalAnswer(BaseModel):
    """Model for LLM final answers"""
    type: Literal["final_answer"]
    value: str

# Perception Models
class RawUserInput(BaseModel):
    """Model for validating web form or user input"""
    dish_name: str | None = Field(
        None, 
        min_length=1, 
        max_length=100,
        description="Name of the dish to cook"
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

class PerceptionError(BaseModel):
    """Model for perception layer errors"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

# Memory Models
class AgentMemory(BaseModel):
    """Model for agent's memory state"""
    # Core state
    dish_name: constr(min_length=1, max_length=100) = ""
    pantry_items: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    available_pantry_items: List[str] = Field(default_factory=list)  # New field for user's available ingredients
    required_ingredients: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    missing_ingredients: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    recipe_steps: List[str] = Field(default_factory=list)
    order_placed: bool = False
    order_id: Optional[str] = None
    order_details: Dict[str, Any] = Field(default_factory=dict)  # Store order details including items and total
    email_sent: bool = False
    user_email: Optional[EmailStr] = None
    
    # Metadata
    current_state: str = "initial"  # Track process state
    last_action: Optional[str] = None
    last_action_status: Optional[str] = None
    retries: int = 0
    last_error: Optional[str] = None

class MemoryError(BaseModel):
    """Model for memory layer errors"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

# Union type for LLM responses
LLMResponse = Union[ReasoningBlock, FunctionCall, FinalAnswer]

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

class DecisionContext(BaseModel):
    """Model representing the input context for decision making"""
    current_state: Dict[str, Any]
    system_prompt: str

# Action Models
class ErrorResponse(BaseModel):
    """Model for standardized error responses"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

class GetOrderStatusInput(BaseModel):
    """Input for get_order_status tool"""
    order_id: str

class GetOrderStatusOutput(BaseModel):
    """Output from get_order_status tool"""
    order_id: str
    status: str
    items: List[str]
    total: float
