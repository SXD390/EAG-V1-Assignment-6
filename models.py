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

class PlaceOrderInput(BaseModel):
    """Input model for place_order tool"""
    items: List[str]

class PlaceOrderOutput(BaseModel):
    """Output model for place_order tool"""
    order_placed: bool
    order_id: str
    total: float

class GetPantryInput(BaseModel):
    """Input model for get_pantry_items tool"""
    required_ingredients: List[str]

class GetPantryOutput(BaseModel):
    """Output model for get_pantry_items tool"""
    available_ingredients: List[str]

class GetOrderStatusInput(BaseModel):
    """Input model for get_order_status tool"""
    order_id: str

class GetOrderStatusOutput(BaseModel):
    """Output model for get_order_status tool"""
    status: str
    estimated_delivery: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class SendEmailInput(BaseModel):
    """Input model for send_email tool"""
    to: str
    subject: str
    message: str

class SendEmailOutput(BaseModel):
    """Output model for send_email tool"""
    message_id: str

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
    user_email: Optional[EmailStr] = None

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

# Decision Models
class ActionType(str, Enum):
    """Enum for different types of actions"""
    FETCH_RECIPE = "fetch_recipe"
    GET_PANTRY = "get_pantry"
    PLACE_ORDER = "place_order"
    SEND_EMAIL = "send_email"
    DISPLAY_RECIPE = "display_recipe"
    CHECK_ORDER_STATUS = "check_order_status"
    INVALID_INPUT = "invalid_input"

# Union type for LLM responses
LLMResponse = Union[ReasoningBlock, FunctionCall, FinalAnswer]

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

class CheckOrderStatusParams(BaseModel):
    """Parameters for checking order status"""
    order_id: Optional[str] = None

class CheckOrderStatusOutput(BaseModel):
    """Output for order status check"""
    order_exists: bool
    order_id: Optional[str] = None
    message: str

class PantryCheckInput(BaseModel):
    """Input model for checking pantry against required ingredients"""
    required_ingredients: List[str]

class PantryCheckOutput(BaseModel):
    """Output model for pantry check results"""
    available_ingredients: List[str]
    missing_ingredients: List[str]
    message: str

# Union type for all action parameters
ActionParams = Union[
    FetchRecipeParams,
    GetPantryInput,
    CheckIngredientsParams,
    PlaceOrderInput,
    PlaceOrderParams,
    SendEmailInput,
    SendEmailParams,
    DisplayRecipeParams,
    PantryCheckInput,
    CheckOrderStatusParams,
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
    total: float  # Adding total price field

class ErrorResponse(BaseModel):
    """Model for standardized error responses"""
    error_type: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
