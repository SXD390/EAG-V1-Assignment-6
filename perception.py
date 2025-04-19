from typing import Dict, Any, List, Optional
import logging
from models import UserIntent, PerceptionError, RawUserInput, LLMResponse
from google import genai
import json

# Get logger for this module
logger = logging.getLogger(__name__)

class PerceptionLayer:
    def __init__(self, llm_client: genai.Client):
        logger.debug("Initializing PerceptionLayer")
        self.llm_client = llm_client
        self.last_dish_name = None  # Store last valid dish name

    async def parse_input(self, user_input: dict) -> UserIntent:
        """Parse and validate user input into structured format using LLM"""
        logger.info("Parsing user input")
        
        try:
            # First validate the raw input structure
            raw_input = RawUserInput.model_validate(user_input)
            
            # Update last_dish_name if new one provided
            if raw_input.dish_name:
                self.last_dish_name = raw_input.dish_name
                logger.debug(f"Updated dish name: {self.last_dish_name}")

            # Use LLM to enhance understanding if needed
            if raw_input.dish_name:
                enhanced_input = await self._enhance_understanding(raw_input)
                if raw_input.dish_name:
                    self.last_dish_name = raw_input.dish_name

            # Then validate and convert to UserIntent
            intent = UserIntent(
                dish_name=self.last_dish_name or raw_input.dish_name or "",  # Use last valid dish name if available
                user_email=raw_input.user_email or None
            )
            
            return intent
            
        except Exception as e:
            logger.error(f"Error parsing user input: {e}", exc_info=True)
            error = PerceptionError(
                error_type="ValidationError",
                message=f"Invalid input format: {str(e)}",
                details={"input_data": user_input}
            )
            raise ValueError(error.model_dump_json())

    async def _enhance_understanding(self, raw_input: RawUserInput) -> UserIntent:
        """Enhance understanding of user input using LLM"""
        logger.debug(f"Enhancing understanding of raw input: {raw_input}")
        
        # Create prompt for LLM
        prompt = f"""Given the following user input, extract the dish name if present.
If no dish name is present, return null for that field.

User Input: {raw_input.dish_name}

Respond in the following JSON format:
{{
    "dish_name": string or null
}}

Only include the JSON response, no other text."""

        try:
            # Get LLM response using the correct method
            response = await self._generate_with_timeout(prompt)
            enhanced = response.text.strip()
            
            # Clean up response text
            if enhanced.startswith("```json"):
                enhanced = enhanced[7:]
            elif enhanced.startswith("```"):
                enhanced = enhanced[3:]
            if enhanced.endswith("```"):
                enhanced = enhanced[:-3]
            enhanced = enhanced.strip()
            
            # Parse response
            try:
                parsed = json.loads(enhanced)
                logger.debug(f"Parsed LLM response: {parsed}")
                
                # Create UserIntent with parsed values
                return UserIntent(
                    dish_name=parsed.get("dish_name"),
                    user_email=raw_input.user_email
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.error(f"Raw response: {enhanced}")
                # Return original input on parse failure
                return UserIntent(
                    dish_name=raw_input.dish_name,
                    user_email=raw_input.user_email
                )
                
        except Exception as e:
            logger.error(f"Error in LLM enhancement: {e}")
            # Return original input on any error
            return UserIntent(
                dish_name=raw_input.dish_name,
                user_email=raw_input.user_email
            )

    async def _generate_with_timeout(self, prompt: str, timeout: int = 30) -> Any:
        """Generate LLM response with timeout"""
        import asyncio
        
        try:
            # Add delay to prevent throttling
            await asyncio.sleep(2)
            
            # Run LLM generation in thread pool
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.llm_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt
                    )
                ),
                timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            logger.error("LLM generation timed out")
            raise
        except Exception as e:
            logger.error(f"Error in LLM generation: {e}")
            raise

    async def get_dish_name(self) -> str:
        """Get the dish name from user input"""
        print("\nWhat dish would you like to make? (e.g. 'pasta carbonara' or 'chicken curry')")
        import sys
        dish_name = sys.stdin.readline().strip().lower()
        return dish_name

    async def get_pantry_items(self) -> List[str]:
        """Get pantry items from user input with validation."""
        try:
            # Get pantry items from LLM response
            response = await self._generate_with_timeout(
                "Please list the items in your pantry, one per line. Enter 'done' when finished."
            )
            
            if not response or not response.content:
                logger.warning("No pantry items received from LLM")
                return []
                
            # Parse items from response
            items = []
            for line in response.content[0].text.split('\n'):
                item = line.strip().lower()
                if item and item != 'done':
                    items.append(item)
                    
            # Validate items
            if not items:
                logger.warning("No valid pantry items found in response")
                return []
                
            return items
            
        except Exception as e:
            logger.error(f"Error getting pantry items: {e}", exc_info=True)
            return []

    async def get_email(self) -> str:
        """Get user's email address with basic validation"""
        while True:
            print("\nPlease enter your email address for order notifications:")
            import sys
            email = sys.stdin.readline().strip()
            if "@" in email and "." in email:  # Basic email validation
                return email
            print("Invalid email format. Please try again.") 