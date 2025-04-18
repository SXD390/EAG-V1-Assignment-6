from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    """Model representing parsed user input"""
    dish_name: str = Field(..., description="Name of the dish user wants to cook")
    pantry_items: List[str] = Field(default_factory=list, description="List of ingredients user has")
    user_email: EmailStr = Field(..., description="User's email for notifications")

class PerceptionError(BaseModel):
    """Model for standardized error responses"""
    error_type: str = Field(..., description="Type of error encountered")
    message: str = Field(..., description="Error message")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Raw input that caused the error")

class PerceptionLayer:
    def __init__(self):
        logger.debug("Initializing PerceptionLayer")

    def parse_input(self, user_input: dict) -> UserIntent:
        """Parse and validate user input into structured format"""
        logger.info("Parsing user input")
        logger.debug(f"Raw user input: {user_input}")
        
        try:
            # First validate the raw input structure
            raw_input = RawUserInput.model_validate(user_input)
            logger.debug(f"Validated raw input: {raw_input}")

            # Then validate and convert to UserIntent
            intent = UserIntent(
                dish_name=raw_input.dish_name or "",  # Convert None to empty string
                pantry_items=raw_input.pantry_items or [],  # Convert None to empty list
                user_email=raw_input.user_email or ""  # Convert None to empty string
            )
            logger.debug(f"Created UserIntent model: {intent}")
            return intent
            
        except Exception as e:
            logger.error(f"Error parsing user input: {e}", exc_info=True)
            error = PerceptionError(
                error_type="ValidationError",
                message=f"Invalid input format: {str(e)}",
                input_data=user_input
            )
            raise ValueError(error.model_dump_json()) 