from pydantic import BaseModel, Field
from typing import List
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class UserIntent(BaseModel):
    """Model representing parsed user input"""
    dish_name: str = Field(..., description="Name of the dish user wants to cook")
    pantry_items: List[str] = Field(default_factory=list, description="List of ingredients user has")
    user_email: str = Field(..., description="User's email for notifications")

class PerceptionLayer:
    def __init__(self):
        logger.debug("Initializing PerceptionLayer")
        pass

    def parse_input(self, user_input: dict) -> UserIntent:
        """Parse and validate user input into structured format"""
        logger.info("Parsing user input")
        logger.debug(f"Raw user input: {user_input}")
        
        try:
            # Extract and validate fields
            dish_name = user_input.get("dish_name", "")
            logger.debug(f"Extracted dish_name: {dish_name}")
            
            pantry_items = user_input.get("pantry_items", [])
            logger.debug(f"Extracted pantry_items: {pantry_items}")
            
            user_email = user_input.get("user_email", "")
            logger.debug(f"Extracted user_email: {user_email}")
            
            # Create UserIntent model
            intent = UserIntent(
                dish_name=dish_name,
                pantry_items=pantry_items,
                user_email=user_email
            )
            logger.debug(f"Created UserIntent model: {intent}")
            return intent
            
        except Exception as e:
            logger.error(f"Error parsing user input: {e}", exc_info=True)
            raise ValueError(f"Invalid input format: {str(e)}") 