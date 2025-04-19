from typing import Dict, Any, Optional, Union
import logging
from models import (
    ActionType, Decision, ActionPlan,
    ReasoningBlock, FunctionCall, FinalAnswer,
    LLMResponse, PantryCheckInput
)
from google import genai
import json
import asyncio

# Get logger for this module
logger = logging.getLogger(__name__)

class DecisionLayer:
    def __init__(self, llm_client: genai.Client):
        logger.debug("Initializing DecisionLayer")
        self.llm_client = llm_client

    async def decide(self, context: dict, system_prompt: str) -> LLMResponse:
        """Make decisions using LLM based on current context"""
        logger.info("Making decision based on context")
        
        try:
            # Create decision prompt
            prompt = self._create_decision_prompt(context, system_prompt)
            
            # Get LLM response
            response = await self._generate_with_timeout(prompt)
            response_text = response.text
            
            # Parse and validate LLM response
            parsed_response = self._parse_llm_response(response_text)
            
            # Only log essential information about the response
            if parsed_response.type == "reasoning_block":
                logger.info(f"Decision: Reasoning with next action '{parsed_response.next}'")
            elif parsed_response.type == "function_call":
                logger.info(f"Decision: Call function '{parsed_response.function}'")
            else:
                logger.info(f"Decision: Final answer")
            
            return parsed_response

        except Exception as e:
            logger.error(f"Error in decision making: {e}", exc_info=True)
            # On error, return a reasoning block to handle the error
            return ReasoningBlock(
                type="reasoning_block",
                reasoning_type="error_handling",
                steps=[
                    f"Error occurred: {str(e)}",
                    "Attempting to recover from error"
                ],
                verify="Check if error is recoverable",
                next="Retry last action with modified parameters",
                fallback_plan="Reset to last known good state"
            )

    def _create_decision_prompt(self, context: dict, system_prompt: str) -> str:
        """Create a prompt for the LLM based on current context"""
        # Extract relevant information from context
        current_state = context["current_state"]
        task_progress = context["task_progress"]
        recipe_details = context["recipe_details"]
        order_details = context["order_details"]

        # Create a structured prompt
        prompt = f"""{system_prompt}

Current State:
- Status: {current_state['state']}
- Last Action: {current_state['last_action']}
- Action Status: {current_state['last_action_status']}
- Retries: {current_state['retries']}
- Last Error: {current_state['last_error']}

Task Progress:
- Dish: {task_progress['dish_name']}
- Recipe Obtained: {task_progress['recipe_obtained']}
- Order Placed: {task_progress['order_placed']}
- Email Sent: {task_progress['email_sent']}

Recipe Details:
- Required Ingredients: {recipe_details['required_ingredients']}
- Missing Ingredients: {recipe_details['missing_ingredients']}
- Recipe Steps: {recipe_details['recipe_steps']}

Order Details:
- Order ID: {order_details['order_id']}
- User Email: {task_progress.get('user_email', 'Not provided yet')}

Based on this information, what should be the next action? Respond in the required JSON format."""

        return prompt

    def _parse_llm_response(self, response_text: str) -> LLMResponse:
        """Parse and validate LLM response"""
        try:
            # Clean up response text
            cleaned_text = response_text.strip()
            # Remove markdown code block markers if present
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse the JSON response
            response_data = json.loads(cleaned_text)
            logger.debug(f"Parsed LLM response data: {response_data}")
            
            # Get response type
            response_type = response_data.get("type")
            #logger.debug(f"Response type: {response_type}")
            
            if response_type == "reasoning_block":
                # Validate reasoning block fields
                required_fields = ["steps", "verify", "next", "fallback_plan"]
                for field in required_fields:
                    if field not in response_data:
                        raise ValueError(f"Missing required field '{field}' in reasoning block")
                logger.debug(f"Next action from reasoning block: {response_data['next']}")
                return ReasoningBlock(**response_data)
                
            elif response_type == "function_call":
                # Validate function call fields
                if "function" not in response_data:
                    raise ValueError("Missing 'function' field in function call")
                if "parameters" not in response_data:
                    raise ValueError("Missing 'parameters' field in function call")
                
                logger.debug(f"Function to call: {response_data['function']}")
                logger.debug(f"Function parameters: {response_data['parameters']}")
                
                # Validate function parameters based on action type
                function = response_data.get("function")
                parameters = response_data.get("parameters", {})
                
                try:
                    # Try to convert function to ActionType enum
                    action_type = ActionType(function)
                    logger.debug(f"Successfully mapped function to action type: {action_type}")
                except ValueError:
                    logger.error(f"Invalid action type: {function}")
                    raise ValueError(f"Invalid action type: {function}")
                
                if function == ActionType.FETCH_RECIPE.value:
                    from models import FetchRecipeParams
                    parameters["params"] = FetchRecipeParams(**parameters.get("params", {}))
                    logger.debug("Created FetchRecipeParams")
                elif function == ActionType.GET_PANTRY.value:
                    parameters["params"] = PantryCheckInput(**parameters.get("params", {}))
                    logger.debug("Created PantryCheckInput")
                elif function == ActionType.PLACE_ORDER.value:
                    from models import PlaceOrderParams
                    parameters["params"] = PlaceOrderParams(**parameters.get("params", {}))
                    logger.debug("Created PlaceOrderParams")
                elif function == ActionType.SEND_EMAIL.value:
                    from models import SendEmailParams
                    parameters["params"] = SendEmailParams(**parameters.get("params", {}))
                    logger.debug("Created SendEmailParams")
                elif function == ActionType.CHECK_ORDER_STATUS.value:
                    from models import CheckOrderStatusParams
                    parameters["params"] = CheckOrderStatusParams(**parameters.get("params", {}))
                    logger.debug("Created CheckOrderStatusParams")
                elif function == ActionType.DISPLAY_RECIPE.value:
                    from models import DisplayRecipeParams
                    parameters["params"] = DisplayRecipeParams(**parameters.get("params", {}))
                    logger.debug("Created DisplayRecipeParams")
                else:
                    from models import InvalidInputParams
                    parameters["params"] = InvalidInputParams(message=f"Unsupported action type: {function}")
                    logger.warning(f"Created InvalidInputParams for unsupported action: {function}")
                
                response_data["parameters"] = parameters
                return FunctionCall(**response_data)
                
            elif response_type == "final_answer":
                if "value" not in response_data:
                    raise ValueError("Missing 'value' field in final answer")
                logger.debug("Processing final answer response")
                return FinalAnswer(**response_data)
            else:
                logger.error(f"Invalid response type: {response_type}")
                raise ValueError(f"Invalid response type: {response_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response text: {response_text}")
            raise
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
            raise

    async def _generate_with_timeout(self, prompt: str, timeout: int = 30) -> Any:
        """Generate LLM response with timeout"""
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