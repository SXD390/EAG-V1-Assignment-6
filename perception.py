from typing import Dict, Any, List, Optional
import logging
from models import UserIntent, PerceptionError, RawUserInput, LLMResponse
from google import genai

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
        logger.debug(f"Raw user input: {user_input}")
        
        try:
            # First validate the raw input structure
            raw_input = RawUserInput.model_validate(user_input)
            logger.debug(f"Validated raw input: {raw_input}")

            # Update last_dish_name if new one provided
            if raw_input.dish_name:
                self.last_dish_name = raw_input.dish_name

            # Use LLM to enhance understanding if needed
            if raw_input.dish_name:
                enhanced_input = await self._enhance_understanding(raw_input)
                logger.debug(f"Enhanced input: {enhanced_input}")
                raw_input = RawUserInput.model_validate(enhanced_input)
                if raw_input.dish_name:
                    self.last_dish_name = raw_input.dish_name

            # Then validate and convert to UserIntent
            intent = UserIntent(
                dish_name=self.last_dish_name or raw_input.dish_name or "",  # Use last valid dish name if available
                pantry_items=raw_input.pantry_items or [],
                user_email=raw_input.user_email
            )
            logger.debug(f"Created UserIntent model: {intent}")
            return intent
            
        except Exception as e:
            logger.error(f"Error parsing user input: {e}", exc_info=True)
            error = PerceptionError(
                error_type="ValidationError",
                message=f"Invalid input format: {str(e)}",
                details={"input_data": user_input}
            )
            raise ValueError(error.model_dump_json())

    async def _enhance_understanding(self, raw_input: RawUserInput) -> Dict[str, Any]:
        """Use LLM to enhance understanding of user input"""
        try:
            # Create prompt for LLM
            prompt = f"""Analyze this cooking request and extract key information:
Dish: {raw_input.dish_name}
Available Ingredients: {', '.join(raw_input.pantry_items or [])}
Email: {raw_input.user_email or 'Not provided'}

Extract and return ONLY a JSON object with:
1. Normalized dish name (common/standard name)
2. Categorized ingredients
3. Any special dietary requirements implied

Response must be valid JSON with these exact fields:
{{
    "dish_name": "normalized name",
    "pantry_items": ["ingredient1", "ingredient2"],
    "dietary_requirements": ["requirement1", "requirement2"]
}}"""

            # Get LLM response
            response = await self._generate_with_timeout(prompt)
            enhanced = response.text.strip()
            
            # Clean up the response text
            if enhanced.startswith("```json"):
                enhanced = enhanced[7:]
            if enhanced.endswith("```"):
                enhanced = enhanced[:-3]
            enhanced = enhanced.strip()
            
            # Parse LLM response and merge with original input
            try:
                import json
                enhanced_data = json.loads(enhanced)
                
                # Validate the required fields exist
                if not isinstance(enhanced_data, dict):
                    raise ValueError("LLM response is not a JSON object")
                
                # Ensure all values are of correct type
                dish_name = str(enhanced_data.get("dish_name", raw_input.dish_name))
                pantry_items = [str(item) for item in enhanced_data.get("pantry_items", raw_input.pantry_items or [])]
                dietary_requirements = [str(req) for req in enhanced_data.get("dietary_requirements", [])]
                
                return {
                    "dish_name": dish_name,
                    "pantry_items": pantry_items,
                    "user_email": raw_input.user_email,
                    "dietary_requirements": dietary_requirements
                }
            except json.JSONDecodeError as je:
                logger.warning(f"Failed to parse LLM response as JSON: {je}. Response: {enhanced}")
                return raw_input.model_dump()
            except Exception as e:
                logger.warning(f"Error processing LLM response: {e}")
                return raw_input.model_dump()
                
        except Exception as e:
            logger.error(f"Error enhancing input understanding: {e}", exc_info=True)
            # On error, return original input
            return raw_input.model_dump()

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
            response = await self.llm_client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Please list the items in your pantry, one per line. Enter 'done' when finished."
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