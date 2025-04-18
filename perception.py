from typing import Dict, Any
import logging
from models import UserIntent, PerceptionError, RawUserInput

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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