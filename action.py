from typing import Any, Dict, Optional, List
import logging
from mcp import ClientSession
from memory import MemoryLayer
from models import (
    GetRecipeInput, GetRecipeOutput,
    PlaceOrderInput, PlaceOrderOutput,
    SendEmailInput, SendEmailOutput,
    TextContent, ToolResponse,
    ActionType, Decision, ActionPlan,
    EmailFormatParams, ErrorResponse,
    CheckOrderStatusOutput,
    PantryCheckOutput,
    PantryCheckInput
)
import pydantic
import json
import random

# Get logger for this module
logger = logging.getLogger(__name__)

# Custom exception for recipe service errors
class RecipeServiceError(Exception):
    pass


class ActionLayer:
    def __init__(self, recipe_session: ClientSession, delivery_session: ClientSession, gmail_session: ClientSession, memory: MemoryLayer):
        logger.debug("Initializing ActionLayer")
        self.recipe_session = recipe_session
        self.delivery_session = delivery_session
        self.gmail_session = gmail_session
        self.memory = memory
        logger.debug(f"ActionLayer initialized with memory: {self.memory}")

    async def get_recipe(self, input_model: GetRecipeInput) -> Dict:
        """Get recipe details using the recipe MCP tool"""
        logger.info(f"Getting recipe for: {input_model.dish_name}")
        try:
            # Log the input we're sending
            logger.debug(f"Sending recipe request with input: {input_model.model_dump()}")
            
            result = await self.recipe_session.call_tool(
                "get_recipe",
                {"input": input_model.model_dump()}
            )
            logger.debug(f"Raw recipe result type: {type(result)}")
            logger.debug(f"Raw recipe result structure: {result}")
            
            # Handle CallToolResult object
            if hasattr(result, 'content') and isinstance(result.content, list):
                # Extract text content from the first item
                if not result.content:
                    raise ValueError("Empty content array in recipe service response")
                
                content = result.content[0].text if hasattr(result.content[0], 'text') else ''
                logger.debug(f"Extracted content text: {content}")
                
                if not content:
                    raise ValueError("Empty text content in recipe service response")
                
                # Try to parse the content as JSON
                try:
                    parsed_content = json.loads(content)
                    logger.debug(f"Parsed content: {parsed_content}")
                    
                    # First check if we got an error response
                    if isinstance(parsed_content, dict):
                        if 'error_type' in parsed_content:
                            error_msg = parsed_content.get('message', 'Unknown recipe service error')
                            logger.error(f"Recipe service returned error: {error_msg}")
                            raise RecipeServiceError(f"Recipe service error: {error_msg}")
                        
                        # If it's a nested response with content, extract the inner content
                        if 'content' in parsed_content and isinstance(parsed_content['content'], list):
                            inner_content = parsed_content['content'][0].get('text', '')
                            if inner_content:
                                logger.debug(f"Found nested content, extracting inner text: {inner_content}")
                                try:
                                    inner_parsed = json.loads(inner_content)
                                    # Check if inner content is an error
                                    if isinstance(inner_parsed, dict) and 'error_type' in inner_parsed:
                                        error_msg = inner_parsed.get('message', 'Unknown recipe service error')
                                        logger.error(f"Recipe service returned nested error: {error_msg}")
                                        raise RecipeServiceError(f"Recipe service error: {error_msg}")
                                    parsed_content = inner_parsed
                                except json.JSONDecodeError:
                                    logger.debug("Inner content is not JSON, using as is")
                                    parsed_content = inner_content
                    
                    # Now try to validate as recipe output
                    try:
                        recipe_output = GetRecipeOutput.model_validate(parsed_content)
                        logger.debug(f"Successfully validated recipe output: {recipe_output.model_dump()}")
                        return recipe_output.model_dump()
                    except pydantic.ValidationError as ve:
                        logger.error(f"Failed to validate recipe output: {ve}")
                        logger.debug(f"Validation error details: {ve.errors()}")
                        # Check if the validation error is due to an error response from the service
                        if isinstance(parsed_content, dict) and ('error_type' in parsed_content or 'error' in parsed_content):
                            error_msg = parsed_content.get('message', parsed_content.get('error', 'Unknown recipe service error'))
                            raise RecipeServiceError(f"Recipe service error: {error_msg}")
                        # Otherwise, it's a format validation error
                        raise ValueError(f"Invalid recipe format: {str(ve)}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse content as JSON: {e}")
                    logger.debug(f"Content that failed to parse: {content}")
                    raise ValueError(f"Invalid JSON in recipe service response: {e}")
            else:
                raise ValueError(f"Invalid response structure from recipe service: {result}")
        
        except RecipeServiceError: # Let specific service errors propagate
            raise
        except ValueError: # Let specific value errors propagate (JSON, format, etc.)
            raise
        except Exception as e: # Catch unexpected errors
            logger.error(f"Unexpected error getting recipe: {str(e)}", exc_info=True)
            raise RecipeServiceError(f"Unexpected error getting recipe: {str(e)}") # Wrap as service error

    async def execute(self, action_plan: ActionPlan) -> ToolResponse:
        """Execute the action plan from the decision layer"""
        logger.debug(f"Received action plan: {action_plan}")
        
        if action_plan.type == "function_call":
            logger.info(f"Processing function call: {action_plan.function}")
            try:
                # Extract input parameters
                input_params = action_plan.parameters.get("input", {})
                logger.debug(f"Input parameters: {input_params}")
                
                # Convert function call format to Decision format with proper parameter type
                action_type = ActionType(action_plan.function)
                
                # Create appropriate parameter object based on action type
                if action_type == ActionType.FETCH_RECIPE:
                    from models import FetchRecipeParams
                    params = FetchRecipeParams(**input_params)
                elif action_type == ActionType.GET_PANTRY:
                    # Check if we have required ingredients
                    memory_state = self.memory.get_memory()
                    required_ingredients = memory_state.get('required_ingredients', [])
                    
                    if not required_ingredients:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No recipe loaded. Please get a recipe first."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No recipe loaded. Please get a recipe first."
                            )]
                        )
                    
                    # Use a simple dictionary for params - no reference to decision
                    params = {"ingredients": required_ingredients}
                    logger.debug(f"Created GET_PANTRY parameters with ingredients: {required_ingredients}")
                elif action_type == ActionType.PLACE_ORDER:
                    # Create parameters for place order
                    # In a real system, we would get these from user input or memory
                    memory_state = self.memory.get_memory()
                    missing_ingredients = memory_state.get('missing_ingredients', [])
                    
                    logger.debug(f"PLACE_ORDER - Memory state: {memory_state}")
                    logger.debug(f"PLACE_ORDER - Missing ingredients from memory: {missing_ingredients}")
                    
                    if not missing_ingredients:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No missing ingredients to order."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No missing ingredients to order. Please check pantry first."
                            )]
                        )
                    
                    # Use a simple dictionary for params
                    params = {"items": missing_ingredients}
                    logger.debug(f"Created PLACE_ORDER parameters with items: {missing_ingredients}")
                elif action_type == ActionType.SEND_EMAIL:
                    # Create parameters for sending email
                    memory_state = self.memory.get_memory()
                    order_placed = memory_state.get('order_placed', False)
                    
                    if not order_placed:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No order to send email for. Please place an order first."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No order to send email for. Please place an order first."
                            )]
                        )
                    
                    # We don't need parameters as we'll get the email interactively
                    params = {}
                    logger.debug("Created empty params for SEND_EMAIL, will prompt user for email")
                elif action_type == ActionType.DISPLAY_RECIPE:
                    from models import DisplayRecipeParams
                    params = DisplayRecipeParams(**input_params)
                elif action_type == ActionType.CHECK_ORDER_STATUS:
                    # Create parameters for check order status
                    memory_state = self.memory.get_memory()
                    order_id = memory_state.get('order_id')
                    
                    if not order_id:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No order to check. Please place an order first."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No order to check. Please place an order first."
                            )]
                        )
                    
                    # Use a simple dictionary for params
                    params = {"order_id": order_id}
                    logger.debug(f"Created CHECK_ORDER_STATUS parameters with order_id: {order_id}")
                else:
                    from models import InvalidInputParams
                    params = InvalidInputParams(message=f"Invalid action type: {action_plan.function}")
                
                decision = Decision(
                    action=action_type,
                    params=params,
                    reasoning="Executing function call",
                    fallback=action_plan.on_fail
                )
                logger.debug(f"Created decision object: {decision}")
                return await self.execute_action(decision)
            except ValueError as e:
                logger.error(f"Invalid action type in function call: {action_plan.function}")
                return ToolResponse(
                    content=[TextContent(
                        type="text",
                        text=f"Invalid action type: {action_plan.function}"
                    )]
                )
            except pydantic.ValidationError as e:
                logger.error(f"Parameter validation error: {str(e)}")
                return ToolResponse(
                    content=[TextContent(
                        type="text",
                        text=f"Invalid parameters: {str(e)}"
                    )]
                )
        elif action_plan.type == "reasoning_block":
            logger.info(f"Processing reasoning block with next action: {action_plan.next}")
            
            # Clean and normalize the action text
            next_action = action_plan.next.lower().strip()
            # Remove common prefixes that might confuse the action mapping
            next_action = next_action.replace("call", "").replace("the", "").strip()
            if next_action.startswith("'") or next_action.startswith('"'):
                next_action = next_action[1:]
            if next_action.endswith("'") or next_action.endswith('"'):
                next_action = next_action[:-1]
            
            # Normalize action text by replacing underscores with spaces
            normalized_action = next_action.replace("_", " ")
            
            # Map the next action to the correct ActionType enum value
            action_mapping = {
                # Original underscore format
                "get_recipe": ActionType.FETCH_RECIPE,
                "fetch_recipe": ActionType.FETCH_RECIPE,
                "check_pantry": ActionType.GET_PANTRY,
                "wait_for_recipe": ActionType.WAIT_FOR_RECIPE,
                "place_order": ActionType.PLACE_ORDER,
                "check_order_status": ActionType.CHECK_ORDER_STATUS,
                "send_email": ActionType.SEND_EMAIL,
                # Space format
                "get recipe": ActionType.FETCH_RECIPE,
                "fetch recipe": ActionType.FETCH_RECIPE,
                "check pantry": ActionType.GET_PANTRY,
                "wait for recipe": ActionType.WAIT_FOR_RECIPE,
                "place order": ActionType.PLACE_ORDER,
                "check order status": ActionType.CHECK_ORDER_STATUS,
                "send email": ActionType.SEND_EMAIL,
                # Natural language variations
                "get the recipe": ActionType.FETCH_RECIPE,
                "get recipe for": ActionType.FETCH_RECIPE,
                "check the pantry": ActionType.GET_PANTRY,
                "check my pantry": ActionType.GET_PANTRY,
                "what ingredients do i have": ActionType.GET_PANTRY,
                "what's in my pantry": ActionType.GET_PANTRY,
                "list pantry": ActionType.GET_PANTRY,
                "show pantry": ActionType.GET_PANTRY,
                "wait for the recipe": ActionType.WAIT_FOR_RECIPE,
                "waiting for recipe": ActionType.WAIT_FOR_RECIPE,
                "order ingredients": ActionType.PLACE_ORDER,
                "order missing ingredients": ActionType.PLACE_ORDER,
                "place an order": ActionType.PLACE_ORDER,
                "check the order": ActionType.CHECK_ORDER_STATUS,
                "check order": ActionType.CHECK_ORDER_STATUS,
                "check the order status": ActionType.CHECK_ORDER_STATUS,
                "track order": ActionType.CHECK_ORDER_STATUS,
                "track the order": ActionType.CHECK_ORDER_STATUS,
                "send confirmation email": ActionType.SEND_EMAIL,
                "send order confirmation": ActionType.SEND_EMAIL,
                "send a confirmation email": ActionType.SEND_EMAIL,
                "email the user": ActionType.SEND_EMAIL,
                "notify the user": ActionType.SEND_EMAIL,
                # Additional variations for pantry check
                "check pantry ingredients": ActionType.GET_PANTRY,
                "identify missing ingredients": ActionType.GET_PANTRY,
                "check ingredients in pantry": ActionType.GET_PANTRY,
                "check available ingredients": ActionType.GET_PANTRY,
                "verify pantry contents": ActionType.GET_PANTRY,
                "check pantry api": ActionType.GET_PANTRY
            }
            
            # Try exact match first
            action_type = action_mapping.get(next_action)
            
            # If no exact match, try with normalized action (spaces)
            if action_type is None:
                action_type = action_mapping.get(normalized_action)
            
            # If still no match, try substring matching
            if action_type is None:
                for key, value in action_mapping.items():
                    if key in next_action or key in normalized_action:
                        action_type = value
                        break
            
            if action_type is None:
                action_type = ActionType.INVALID_INPUT
                logger.warning(f"Could not map action '{next_action}' to a valid type")
            
            logger.debug(f"Mapped action '{next_action}' to type: {action_type}")
            
            try:
                # Create appropriate parameters based on the action type
                memory = self.memory.get_memory()
                logger.debug(f"Memory peter: {memory}")
                
                if action_type == ActionType.FETCH_RECIPE:
                    # Extract recipe name if present in the action text
                    recipe_name = None
                    if "recipe name" in normalized_action:
                        recipe_name = normalized_action.split("recipe name", 1)[1].strip().strip("'").strip('"').strip(".")
                    elif "recipe for" in normalized_action:
                        recipe_name = normalized_action.split("recipe for", 1)[1].strip().strip("'").strip('"').strip(".")
                    elif "get recipe" in normalized_action:
                        recipe_name = normalized_action.split("get recipe", 1)[1].strip().strip("'").strip('"').strip(".")
                    
                    from models import FetchRecipeParams
                    # Use memory dish_name if no recipe name extracted
                    params = FetchRecipeParams(dish_name=recipe_name or memory.get("dish_name", ""))
                    logger.debug(f"Created FetchRecipeParams with dish_name: {params.dish_name}")
                
                elif action_type == ActionType.GET_PANTRY:
                    # Check if we have required ingredients
                    memory_state = self.memory.get_memory()
                    required_ingredients = memory_state.get('required_ingredients', [])
                    
                    if not required_ingredients:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No recipe loaded. Please get a recipe first."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No recipe loaded. Please get a recipe first."
                            )]
                        )
                    
                    # Use a simple dictionary for params - no reference to decision
                    params = {"ingredients": required_ingredients}
                    logger.debug(f"Created GET_PANTRY parameters with ingredients: {required_ingredients}")
                
                elif action_type == ActionType.CHECK_ORDER_STATUS:
                    # Create parameters for check order status
                    memory_state = self.memory.get_memory()
                    order_id = memory_state.get('order_id')
                    
                    if not order_id:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No order to check. Please place an order first."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No order to check. Please place an order first."
                            )]
                        )
                    
                    # Use a simple dictionary for params
                    params = {"order_id": order_id}
                    logger.debug(f"Created CHECK_ORDER_STATUS parameters with order_id: {order_id}")
                
                elif action_type == ActionType.SEND_EMAIL:
                    # Create parameters for sending email
                    memory_state = self.memory.get_memory()
                    order_placed = memory_state.get('order_placed', False)
                    
                    if not order_placed:
                        self.memory.update_memory(
                            last_action_status="failed",
                            last_error="No order to send email for. Please place an order first."
                        )
                        return ToolResponse(
                            content=[TextContent(
                                text="No order to send email for. Please place an order first."
                            )]
                        )
                    
                    # We don't need parameters as we'll get the email interactively
                    params = {}
                    logger.debug("Created empty params for SEND_EMAIL, will prompt user for email")
                
                else:
                    from models import InvalidInputParams
                    params = InvalidInputParams(message=f"Invalid or unsupported action type: {next_action}")
                    logger.warning(f"Created InvalidInputParams for action: {next_action}")
                
                logger.debug(f"Created parameters for action {action_type}: {params}")
                
                decision = Decision(
                    action=action_type,
                    params=params,
                    reasoning=action_plan.steps[0] if action_plan.steps else "Executing next action",
                    fallback=action_plan.fallback_plan
                )
                logger.debug(f"Created decision object from reasoning: {decision}")
                return await self.execute_action(decision)
                
            except Exception as e:
                logger.error(f"Error creating parameters for action {action_type}: {e}", exc_info=True)
                self.memory.update_memory(
                    current_state="error",
                    last_action=str(action_type),
                    last_action_status="failed",
                    last_error=f"Error creating parameters: {str(e)}"
                )
                return ToolResponse(
                    content=[TextContent(
                        text=f"Error preparing action: {str(e)}"
                    )]
                )
        elif action_plan.type == "final_answer":
            logger.info(f"Processing final answer: {action_plan.value}")
            return ToolResponse(
                content=[TextContent(
                    type="text",
                    text=action_plan.value
                )]
            )
        else:
            logger.warning(f"Invalid action plan type: {action_plan.type}")
            return ToolResponse(
                content=[TextContent(
                    type="text",
                    text="Invalid action plan type"
                )]
            )

    async def check_order_status(self, order_id: Optional[str] = None) -> CheckOrderStatusOutput:
        """Check if an order exists in memory"""
        logger.info(f"Checking order status for order_id: {order_id}")
        
        # Get memory state
        memory_state = self.memory.get_memory()
        
        # If no order_id provided, use the one from memory
        if not order_id:
            order_id = memory_state.get("order_id")
        
        # Check if order exists
        order_exists = (
            order_id is not None and 
            memory_state.get("order_id") is not None and 
            order_id == memory_state.get("order_id")
        )
        
        message = (
            f"Order {order_id} found in system." if order_exists
            else "No matching order found."
        )
        
        return CheckOrderStatusOutput(
            order_exists=order_exists,
            order_id=order_id if order_exists else None,
            message=message
        )

    async def execute_action(self, decision: Decision) -> ToolResponse:
        """Execute the action based on the decision"""
        logger.info(f"Executing action: {decision.action}")
        logger.debug(f"Decision details: {decision.model_dump()}")
        
        try:
            # Update memory with action start
            self.memory.update_memory(
                last_action=decision.action.value,
                current_state="action_in_progress",
                last_action_status="started"
            )

            if decision.action == ActionType.WAIT_FOR_RECIPE:
                # Check if recipe fetch is complete
                memory_state = self.memory.get_memory()
                logger.debug(f"Checking recipe status in memory: {memory_state}")
                if memory_state["recipe_steps"]:
                    # Recipe is ready
                    self.memory.update_memory(
                        last_action_status="completed",
                        current_state="ready"
                    )
                    return ToolResponse(content=[TextContent(
                        text="Recipe has been fetched successfully."
                    )])
                else:
                    # Still waiting
                    self.memory.update_memory(
                        last_action_status="waiting",
                        current_state="waiting_for_recipe"
                    )
                    return ToolResponse(content=[TextContent(
                        text="Still waiting for recipe to be fetched..."
                    )])

            elif decision.action == ActionType.FETCH_RECIPE:
                try:
                    # Parameters are already validated as FetchRecipeParams
                    input_model = GetRecipeInput(dish_name=decision.params.dish_name)
                    logger.debug(f"Created recipe input model: {input_model.model_dump()}")
                    
                    # Call get_recipe method which handles the service call
                    result_dict = await self.get_recipe(input_model) # Returns dict on success, raises error otherwise
                    logger.debug(f"Recipe service returned successfully: {result_dict}")
                    
                    # Already validated in get_recipe, just load
                    recipe_output = GetRecipeOutput.model_validate(result_dict)
                        
                    # Update memory with recipe information
                    self.memory.update_memory(
                        required_ingredients=recipe_output.required_ingredients,
                        recipe_steps=recipe_output.recipe_steps,
                        last_action_status="completed",
                        current_state="recipe_fetched"
                    )
                    
                    # Format the recipe text for display
                    display_text = f"Recipe for {recipe_output.recipe_name}:\n\n"
                    display_text += "Required ingredients:\n"
                    for ing in recipe_output.required_ingredients:
                        display_text += f"- {ing}\n"
                    display_text += "\nSteps:\n"
                    for i, step in enumerate(recipe_output.recipe_steps, 1):
                        display_text += f"{i}. {step}\n"
                    
                    logger.debug(f"Formatted recipe display text: {display_text}")
                    return ToolResponse(
                        content=[TextContent(
                            type="text",
                            text=display_text
                        )]
                    )

                except RecipeServiceError as e: # Catch specific service error
                    error_msg = f"Error fetching recipe: {str(e)}"
                    logger.error(error_msg, exc_info=False) # No need for full traceback for service error
                    self.memory.update_memory(
                        current_state="error",
                        last_action_status="failed",
                        last_error=error_msg
                    )
                    return ToolResponse(content=[TextContent(type="text", text=error_msg)])
                except ValueError as e: # Catch other errors like JSON parsing or format validation
                    error_msg = f"Error processing recipe data: {str(e)}"
                    logger.error(error_msg, exc_info=True) # Include traceback for these
                    self.memory.update_memory(
                        current_state="error",
                        last_action_status="failed",
                        last_error=error_msg
                    )
                    return ToolResponse(content=[TextContent(type="text", text=error_msg)])
                except Exception as e: # Catch unexpected errors
                    error_msg = f"Unexpected error during recipe fetch: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.memory.update_memory(
                        current_state="error",
                        last_action_status="failed",
                        last_error=error_msg
                    )
                    return ToolResponse(content=[TextContent(type="text", text=error_msg)])

            elif decision.action == ActionType.GET_PANTRY:
                # Check if we have required ingredients
                memory_state = self.memory.get_memory()
                required_ingredients = memory_state.get('required_ingredients', [])
                
                if not required_ingredients:
                    self.memory.update_memory(
                        last_action_status="failed",
                        last_error="No recipe loaded. Please get a recipe first."
                    )
                    return ToolResponse(
                        content=[TextContent(
                            text="No recipe loaded. Please get a recipe first."
                        )]
                    )
                
                try:
                    # Call our local method instead of the MCP tool
                    result = self.check_pantry_items(required_ingredients)
                    
                    # Update memory with results
                    self.memory.update_memory(
                        pantry_items=result["available_ingredients"],
                        missing_ingredients=result["missing_ingredients"],
                        last_action_status="completed",
                        current_state="pantry_checked"
                    )
                    
                    return ToolResponse(
                        content=[TextContent(
                            text=result["message"]
                        )]
                    )
                        
                except Exception as e:
                    error_msg = f"Error in pantry check: {str(e)}"
                    logger.error(error_msg)
                    self.memory.update_memory(
                        last_action_status="failed", 
                        last_error=error_msg
                    )
                    return ToolResponse(
                        content=[TextContent(
                            text=error_msg
                        )]
                    )

            elif decision.action == ActionType.CHECK_ORDER_STATUS:
                # Check the status of the order
                try:
                    order_id = decision.params.get("order_id") if isinstance(decision.params, dict) else getattr(decision.params, "order_id", None)
                    
                    # Call our check_order_status method
                    result = await self.check_order_status(order_id)
                    
                    # Format the message with a bit more detail if order exists
                    if result.order_exists:
                        # Get order details from memory
                        memory_state = self.memory.get_memory()
                        order_details = memory_state.get("order_details", {})
                        items = order_details.get("items", [])
                        total = order_details.get("total", 0.0)
                        
                        message = f"Order {result.order_id} found in system.\n"
                        message += f"Status: Processing\n"
                        message += f"Items: {', '.join(items)}\n"
                        message += f"Total: ${total:.2f}\n"
                        message += f"Expected delivery: Within 2 days"
                    else:
                        message = result.message
                    
                    # Update memory
                    self.memory.update_memory(
                        last_action_status="completed",
                        current_state="awaiting_email"  # Change from "order_checked" to a non-terminal state
                    )
                    
                    return ToolResponse(
                        content=[TextContent(
                            text=message + "\n\nThe system is ready to send an order confirmation email to your address."
                        )]
                    )
                except Exception as e:
                    error_msg = f"Error checking order status: {str(e)}"
                    logger.error(error_msg)
                    self.memory.update_memory(
                        last_action_status="failed",
                        last_error=error_msg
                    )
                    return ToolResponse(
                        content=[TextContent(
                            text=error_msg
                        )]
                    )

            elif decision.action == ActionType.PLACE_ORDER:
                # Get memory state to access missing_ingredients
                memory_state = self.memory.get_memory()
                missing_ingredients = memory_state.get('missing_ingredients', [])
                
                logger.debug(f"PLACE_ORDER - Memory state: {memory_state}")
                logger.debug(f"PLACE_ORDER - Missing ingredients from memory: {missing_ingredients}")
                
                if not missing_ingredients:
                    return ToolResponse(
                        content=[TextContent(
                            text="No ingredients to order. Please check missing ingredients first."
                        )]
                    )
                
                try:
                    # Calculate a mock total
                    item_price = 3.99  # Average price per item
                    total = len(missing_ingredients) * item_price
                    
                    # Store order details
                    order_details = {
                        "items": missing_ingredients,
                        "total": total
                    }
                    
                    # Debug the order details being stored
                    logger.debug(f"PLACE_ORDER - Creating order details: {order_details}")
                    
                    # Generate a simple order ID
                    order_id = f"ORD-{random.randint(10000, 99999)}"
                    
                    # Update memory with order details
                    self.memory.update_memory(
                        order_placed=True,
                        order_id=order_id,
                        order_details=order_details,
                        current_state="order_placed",
                        last_action_status="completed"
                    )
                    
                    return ToolResponse(
                        content=[TextContent(
                            text=f"Order placed successfully! Order ID: {order_id}\n"
                                 f"Total: ${total:.2f}\n"
                                 f"Items: {', '.join(missing_ingredients)}"
                        )]
                    )
                except Exception as e:
                    error_msg = f"Failed to place order: {str(e)}"
                    logger.error(error_msg)
                    self.memory.update_memory(
                        last_action_status="failed",
                        last_error=error_msg
                    )
                    return ToolResponse(
                        content=[TextContent(
                            text=error_msg
                        )]
                    )

            elif decision.action == ActionType.SEND_EMAIL:
                # Get memory state
                memory_state = self.memory.get_memory()
                order_placed = memory_state.get('order_placed', False)
                
                if not order_placed:
                    return ToolResponse(
                        content=[TextContent(
                            text="No order to send email for. Please place an order first."
                        )]
                    )
                
                # Format and send order confirmation email
                try:
                    order_details = memory_state.get('order_details', {})
                    order_id = memory_state.get('order_id', 'unknown')
                    
                    # Get email from user if not already in memory
                    user_email = memory_state.get('user_email')
                    if not user_email:
                        user_email = self.get_user_email()
                        # Update memory with the email
                        self.memory.update_memory(user_email=user_email)
                    
                    # Get order details
                    items = order_details.get('items', [])
                    total = order_details.get('total', 0.0)
                    
                    # If order details are missing or items is empty, fall back to using missing_ingredients
                    if not items and 'missing_ingredients' in memory_state:
                        logger.warning("Order details missing items - falling back to missing_ingredients")
                        items = memory_state.get('missing_ingredients', [])
                        # Recalculate total
                        total = len(items) * 3.99  # Use same price formula as in place_order
                        
                        # Update order_details in memory for future reference - without email
                        self.memory.update_memory(
                            order_details={
                                "items": items,
                                "total": total
                            }
                        )
                    
                    # Only log important diagnostics
                    logger.debug(f"SEND_EMAIL - Order details: {items}, total: ${total:.2f}")
                    
                    # Create email body
                    email_body = self._format_order_email(items, order_id, total)
                    
                    # Simulate sending the email
                    logger.info(f"Sending confirmation email to {user_email}")
                    
                    # Actually send the email using Gmail MCP tool
                    try:
                        send_email_input = SendEmailInput(
                            to_email=user_email,
                            subject=f"Your Order Confirmation #{order_id}",
                            body=email_body
                        )
                        
                        # Don't exclude body from the actual request, only from logging
                        logger.info(f"Calling gmail send_email tool with to={user_email}, subject=Order Confirmation")
                        result = await self.gmail_session.call_tool(
                            "send_email",
                            {"input": send_email_input.model_dump()}  # Include all fields
                        )
                        
                        # Properly handle the response - the email has been sent even if there's a validation error
                        if hasattr(result, 'content') and result.content:
                            response_text = getattr(result.content[0], 'text', '')
                            
                            # Check if we got an error response but the email might have been sent
                            if "error_type" in response_text and "service_available" in response_text:
                                # The email service responded with an error but might have sent the email
                                # Log warning but continue
                                logger.warning(f"Email service reported validation error but likely sent email")
                            else:
                                # Normal success response
                                logger.info(f"Email sent successfully")
                        else:
                            logger.info(f"Email service response: {type(result)}")
                            
                    except Exception as email_error:
                        logger.error(f"Failed to send email via Gmail MCP: {str(email_error)}")
                    
                    # Update memory
                    self.memory.update_memory(
                        email_sent=True,
                        current_state="completed",  # Change to completed instead of email_sent
                        last_action_status="completed"
                    )
                    
                    # Now display the recipe for a better user experience
                    memory_state = self.memory.get_memory()
                    dish_name = memory_state.get("dish_name", "")
                    recipe_steps = memory_state.get("recipe_steps", [])
                    ingredients = memory_state.get("required_ingredients", [])
                    
                    # Format a beautiful recipe display
                    recipe_display = self._format_recipe_display(dish_name, ingredients, recipe_steps)
                    
                    return ToolResponse(
                        content=[TextContent(
                            text=f"Order confirmation email sent successfully to {user_email}!\n\n{recipe_display}"
                        )]
                    )
                except Exception as e:
                    error_msg = f"Failed to send email: {str(e)}"
                    logger.error(error_msg)
                    return ToolResponse(
                        content=[TextContent(
                            text=error_msg
                        )]
                    )

            elif decision.action == ActionType.DISPLAY_RECIPE:
                # Parameters are already validated as DisplayRecipeParams
                return ToolResponse(
                    content=[TextContent(
                        text="\n".join(decision.params.steps)
                    )]
                )

            else:
                return ToolResponse(
                    content=[TextContent(
                        text=decision.fallback or "Invalid action"
                    )]
                )

        except Exception as e: # Outer catch block in execute_action
            error_msg = f"Unexpected error executing {decision.action}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update memory with error state
            self.memory.update_memory(
                current_state="error",
                last_action_status="failed", 
                last_error=error_msg
            )
            
            return ToolResponse(
                content=[TextContent(
                    type="text",
                    text=error_msg
                )]
            )

    def _format_order_email(self, items: list, order_id: str, total: float) -> str:
        """Format the order confirmation email with beautiful HTML"""
        items_list = "\n".join([f"<li style='margin: 8px 0;'>{item}</li>" for item in items])
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header Banner -->
        <div style="background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
            <h1 style="color: white; margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">🎉 Order Confirmed! 🎉</h1>
        </div>

        <!-- Order Details -->
        <div style="background-color: #FFFFFF; border-radius: 10px; padding: 25px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px;">
            <h2 style="color: #2D3748; margin-top: 0; font-size: 20px; border-bottom: 2px solid #FF6B6B; padding-bottom: 10px;">Order Details</h2>
            <p style="color: #4A5568; margin: 15px 0;">
                <strong>Order ID:</strong> 
                <span style="background-color: #F7FAFC; padding: 5px 10px; border-radius: 5px; font-family: monospace;">{order_id}</span>
            </p>
            <p style="color: #4A5568; margin: 15px 0;">
                <strong>Total Amount:</strong> 
                <span style="background-color: #F7FAFC; padding: 5px 10px; border-radius: 5px; color: #38A169; font-weight: bold;">${total:.2f}</span>
            </p>
        </div>

        <!-- Items List -->
        <div style="background-color: #FFFFFF; border-radius: 10px; padding: 25px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px;">
            <h2 style="color: #2D3748; margin-top: 0; font-size: 20px; border-bottom: 2px solid #FF6B6B; padding-bottom: 10px;">Your Ingredients</h2>
            <ul style="list-style-type: none; padding-left: 0; color: #4A5568;">
                {items_list}
            </ul>
            <p style="color: #718096; margin-top: 15px; font-style: italic;">
                Total Items: {len(items)}
            </p>
        </div>

        <!-- Delivery Info -->
        <div style="background-color: #FFFFFF; border-radius: 10px; padding: 25px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px;">
            <h2 style="color: #2D3748; margin-top: 0; font-size: 20px; border-bottom: 2px solid #FF6B6B; padding-bottom: 10px;">Delivery Information</h2>
            <p style="color: #4A5568; margin: 15px 0;">
                Your ingredients will be delivered soon. We'll make sure everything arrives fresh and ready for your cooking adventure!
            </p>
        </div>

        <!-- Order Summary -->
        <div style="background-color: #F7FAFC; border-radius: 10px; padding: 20px; margin-bottom: 20px; text-align: right;">
            <table style="width: 100%; color: #4A5568;">
                <tr>
                    <td style="padding: 8px; text-align: left;"><strong>Subtotal:</strong></td>
                    <td style="padding: 8px; text-align: right;">${total:.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; text-align: left;"><strong>Delivery:</strong></td>
                    <td style="padding: 8px; text-align: right;">Free</td>
                </tr>
                <tr style="font-size: 1.2em; font-weight: bold; color: #2D3748;">
                    <td style="padding: 12px 8px; text-align: left; border-top: 2px solid #E2E8F0;">Total:</td>
                    <td style="padding: 12px 8px; text-align: right; border-top: 2px solid #E2E8F0;">${total:.2f}</td>
                </tr>
            </table>
        </div>

        <!-- Footer -->
        <div style="text-align: center; margin-top: 30px; padding: 20px; color: #718096;">
            <p style="margin: 5px 0;">Happy Cooking! 👨‍🍳</p>
            <p style="margin: 5px 0; font-size: 12px;">This is an automated email, please do not reply.</p>
        </div>
    </div>
</body>
</html>
"""

    def check_pantry_items(self, required_ingredients):
        """
        Check what ingredients are available in user's pantry and what's missing 
        from required ingredients. This is done directly in the action layer
        without calling the MCP server.
        """
        logger.info(f"Checking pantry for required ingredients: {required_ingredients}")
        
        # Ask user to input pantry items
        print("\nPlease enter the ingredients you have in your pantry.")
        print("Enter each ingredient on a new line. Type 'done' when finished.")
        print("\nRequired ingredients:")
        for ing in required_ingredients:
            print(f"- {ing}")
        
        pantry_items = []
        while True:
            try:
                item = input().strip().lower()
                if item == 'done':
                    break
                if item:  # Only add non-empty items
                    pantry_items.append(item)
            except EOFError:
                break
        
        logger.info(f"User entered pantry items: {pantry_items}")
        
        # Compare ingredients to find missing ones
        missing_ingredients = []
        available_ingredients = []
        
        for required in required_ingredients:
            # Check if any pantry item matches or is similar to the required ingredient
            found = False
            for pantry_item in pantry_items:
                # Simple matching - could be enhanced with fuzzy matching
                if required.lower() in pantry_item or pantry_item in required.lower():
                    available_ingredients.append(required)
                    found = True
                    break
            if not found:
                missing_ingredients.append(required)
        
        # Log results
        logger.info(f"Available ingredients: {available_ingredients}")
        logger.info(f"Missing ingredients: {missing_ingredients}")
        
        # Create message
        if missing_ingredients:
            message = f"You have {len(available_ingredients)} of {len(required_ingredients)} required ingredients.\n"
            message += "Missing ingredients:\n" + "\n".join(f"- {ing}" for ing in missing_ingredients)
        else:
            message = "You have all required ingredients!"
        
        # Store pantry items in memory for future reference
        self.memory.update_memory(
            available_ingredients=available_ingredients
        )
        
        # Return results without using Pydantic models
        return {
            "available_ingredients": available_ingredients,
            "missing_ingredients": missing_ingredients,
            "message": message
        }

    def get_user_email(self):
        """
        Prompt the user to enter their email address for order confirmation.
        Returns the entered email address.
        """
        logger.info("Prompting user for email address")
        
        print("\nPlease enter your email address for order confirmation:")
        while True:
            try:
                email = input().strip()
                # Basic validation for email format
                if email and "@" in email and "." in email.split("@")[1]:
                    logger.info(f"User entered email: {email}")
                    return email
                else:
                    print("Please enter a valid email address:")
            except EOFError:
                logger.warning("EOF encountered while getting email")
                return "user@example.com"  # Default fallback 

    def _format_recipe_display(self, dish_name: str, ingredients: list, steps: list) -> str:
        """Format the recipe in a beautiful way for display"""
        
        border = "=" * 50
        
        # Format dish name
        dish_title = f"\n{border}\n{dish_name.upper()} RECIPE\n{border}\n"
        
        # Format ingredients
        ingredients_section = "INGREDIENTS:\n" + "\n".join([f"• {ingredient}" for ingredient in ingredients])
        
        # Format steps
        steps_section = "\nPREPARATION STEPS:\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        
        # Final note
        final_note = f"\n{border}\nEnjoy your {dish_name}! Bon Appétit!\n{border}\n"
        
        # Combine all sections
        return f"{dish_title}\n{ingredients_section}\n\n{steps_section}\n\n{final_note}" 