from typing import Dict, Any, List
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

    async def get_dish_name(self) -> str:
        """Get the dish name from user input"""
        print("\nWhat dish would you like to make? (e.g. 'pasta carbonara' or 'chicken curry' for testing)")
        import sys
        dish_name = sys.stdin.readline().strip().lower()
        return dish_name

    async def get_pantry_items(self, required_ingredients: List[str]) -> List[str]:
        """Get user's available ingredients based on recipe requirements"""
        print("\nFor this recipe, you'll need:")
        for i, ingredient in enumerate(required_ingredients, 1):
            print(f"{i}. {ingredient}")

        print("\nEnter the numbers of ingredients you ALREADY HAVE (separated by spaces):")
        while True:
            try:
                import sys
                available_nums = sys.stdin.readline().strip().split()
                available_nums = [int(num) for num in available_nums if 1 <= int(num) <= len(required_ingredients)]
                return [required_ingredients[i-1] for i in available_nums]
            except ValueError:
                print("Please enter valid numbers separated by spaces. Try again:")

    async def get_email(self) -> str:
        """Get user's email address with basic validation"""
        while True:
            print("\nPlease enter your email address for order notifications:")
            import sys
            email = sys.stdin.readline().strip()
            if "@" in email and "." in email:  # Basic email validation
                return email
            print("Invalid email format. Please try again.") 