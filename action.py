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
    GetPantryInput, GetPantryOutput,
    CheckOrderStatusOutput,
    PantryCheckOutput,
    PantryCheckInput
)
import pydantic
import json

# Get logger for this module
logger = logging.getLogger(__name__)


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
            result = await self.recipe_session.call_tool(
                "get_recipe",
                {"input": input_model.model_dump()}
            )
            logger.debug(f"Raw recipe result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error getting recipe: {str(e)}", exc_info=True)
            raise

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
                    from models import PantryCheckInput
                    params = PantryCheckInput(**input_params)
                elif action_type == ActionType.PLACE_ORDER:
                    from models import PlaceOrderParams
                    params = PlaceOrderParams(**input_params)
                elif action_type == ActionType.SEND_EMAIL:
                    from models import SendEmailParams
                    params = SendEmailParams(**input_params)
                elif action_type == ActionType.DISPLAY_RECIPE:
                    from models import DisplayRecipeParams
                    params = DisplayRecipeParams(**input_params)
                elif action_type == ActionType.CHECK_ORDER_STATUS:
                    from models import CheckOrderStatusParams
                    params = CheckOrderStatusParams(**input_params)
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
                # Space format
                "get recipe": ActionType.FETCH_RECIPE,
                "fetch recipe": ActionType.FETCH_RECIPE,
                "check pantry": ActionType.GET_PANTRY,
                # Natural language variations
                "get the recipe": ActionType.FETCH_RECIPE,
                "get recipe for": ActionType.FETCH_RECIPE,
                "check the pantry": ActionType.GET_PANTRY,
                "check my pantry": ActionType.GET_PANTRY,
                "what ingredients do i have": ActionType.GET_PANTRY,
                "what's in my pantry": ActionType.GET_PANTRY,
                "list pantry": ActionType.GET_PANTRY,
                "show pantry": ActionType.GET_PANTRY,
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
                    params = FetchRecipeParams(dish_name=recipe_name or getattr(memory, 'dish_name', ''))
                    logger.debug(f"Created FetchRecipeParams with dish_name: {params.dish_name}")
                
                elif action_type == ActionType.GET_PANTRY:
                    try:
                        # Create input model for check_pantry
                        recipe = self.memory.get("recipe")
                        if not recipe:
                            self.memory.update({"last_error": "No recipe loaded. Please get a recipe first."})
                            return "No recipe loaded. Please get a recipe first."

                        required_ingredients = recipe.get("ingredients", [])
                        if not required_ingredients:
                            self.memory.update({"last_error": "No ingredients found in recipe."})
                            return "No ingredients found in recipe."

                        input_model = PantryCheckInput(ingredients=required_ingredients)
                        
                        # Call check_pantry tool
                        result = self.recipe_session.call_tool("check_pantry", input_model)
                        if not result:
                            raise ValueError("Empty response from check_pantry tool")

                        # Parse the response
                        if isinstance(result, dict):
                            # Handle direct dictionary response
                            if isinstance(result, PantryCheckOutput):
                                output = result
                            else:
                                output = PantryCheckOutput.model_validate(result)
                        else:
                            # Try to parse as JSON if it's a string
                            output = PantryCheckOutput.model_validate_json(str(result))

                        # Update memory with results
                        self.memory.update({
                            "pantry_items": output.available_ingredients,
                            "missing_ingredients": output.missing_ingredients,
                            "last_action_status": "completed",
                            "last_error": None
                        })

                        return output.message

                    except Exception as e:
                        error_msg = f"Error checking pantry: {str(e)}"
                        self.memory.update({
                            "last_error": error_msg,
                            "last_action_status": "failed"
                        })
                        return error_msg
                
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
        
        # If no order_id provided, use the one from memory
        if not order_id:
            order_id = self.memory.order_id
        
        # Check if order exists
        order_exists = (
            order_id is not None and 
            self.memory.order_id is not None and 
            order_id == self.memory.order_id
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
        """Execute a single action based on the decision"""
        logger.info(f"Executing action: {decision.action}")
        
        try:
            # Update memory with current action before execution
            self.memory.update_memory(
                last_action=decision.action.value,
                current_state="action_in_progress",
                last_action_status="started"
            )

            if decision.action == ActionType.GET_PANTRY:
                # Check if we have required ingredients
                memory_state = self.memory.get_memory()
                required_ingredients = getattr(memory_state, 'required_ingredients', [])
                
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
                
                # Create input model for check_pantry tool
                input_model = PantryCheckInput(
                    required_ingredients=required_ingredients
                )
                
                try:
                    # Call the check_pantry tool
                    result = await self.recipe_session.call_tool(
                        "check_pantry",
                        {"input": input_model.model_dump()}
                    )
                    
                    if isinstance(result, dict) and 'content' in result and result['content']:
                        try:
                            # Parse the response content
                            content_text = result['content'][0].get('text', '')
                            output = PantryCheckOutput.model_validate_json(content_text)
                            
                            # Update memory with results
                            self.memory.update_memory(
                                pantry_items=output.available_ingredients,
                                missing_ingredients=output.missing_ingredients,
                                last_action_status="completed"
                            )
                            
                            return ToolResponse(
                                content=[TextContent(
                                    text=output.message
                                )]
                            )
                        except Exception as e:
                            error_msg = f"Error parsing pantry check response: {str(e)}"
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
                except Exception as e:
                    error_msg = f"Error calling check_pantry tool: {str(e)}"
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
                # Get order status
                order_id = getattr(decision.params, 'order_id', None)
                result = await self.check_order_status(order_id)
                
                return ToolResponse(
                    content=[TextContent(
                        text=result.message
                    )]
                )

            elif decision.action == ActionType.FETCH_RECIPE:
                # Parameters are already validated as FetchRecipeParams
                input_model = GetRecipeInput(dish_name=decision.params.dish_name)
                
                # Call tool with properly nested input
                result = await self.recipe_session.call_tool(
                    "get_recipe",
                    {"input": input_model.model_dump()}
                )
                
                # Parse the response using Pydantic model
                if hasattr(result, 'content') and result.content:
                    try:
                        # First parse: Get the inner JSON string
                        first_parse = json.loads(result.content[0].text)
                        
                        # Second parse: Parse the actual model data
                        inner_json = json.loads(first_parse['content'][0]['text'])
                        
                        # Validate against GetRecipeOutput model
                        recipe_output = GetRecipeOutput.model_validate(inner_json)
                        
                        # Update memory with recipe information
                        self.memory.update_memory(
                            required_ingredients=recipe_output.required_ingredients,
                            recipe_steps=recipe_output.recipe_steps
                        )
                        
                        # Format the recipe text for display
                        display_text = f"Recipe for {input_model.dish_name}:\n\n"
                        display_text += "Required ingredients:\n"
                        for ing in recipe_output.required_ingredients:
                            display_text += f"- {ing}\n"
                        display_text += "\nSteps:\n"
                        for i, step in enumerate(recipe_output.recipe_steps, 1):
                            display_text += f"{i}. {step}\n"
                        
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=display_text
                            )]
                        )
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error: {je}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=f"Error decoding recipe response: {str(je)}"
                            )]
                        )
                    except pydantic.ValidationError as ve:
                        logger.error(f"Validation error: {ve}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=f"Error validating recipe response: {str(ve)}"
                            )]
                        )
                    except Exception as e:
                        logger.error(f"Error parsing recipe response: {e}", exc_info=True)
                        error_response = ErrorResponse(
                            error_type="ParseError",
                            message=f"Error parsing recipe response: {str(e)}",
                            details={"raw_text": result.content[0].text if result.content else None}
                        )
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=error_response.model_dump_json()
                            )]
                        )
                
                return ToolResponse(
                    content=[TextContent(
                        type="text",
                        text="No recipe data received"
                    )]
                )

            elif decision.action == ActionType.PLACE_ORDER:
                if not self.memory.missing_ingredients:
                    return ToolResponse(
                        content=[TextContent(
                            text="No ingredients to order. Please check missing ingredients first."
                        )]
                    )
                
                # Place order using order MCP tool
                order_result = self.order_tool.place_order(
                    items=self.memory.missing_ingredients,
                    email=decision.params.email
                )
                
                if not order_result.order_placed:
                    return ToolResponse(
                        content=[TextContent(
                            text="Failed to place order. Please try again."
                        )]
                    )
                
                # Update memory with order details
                self.memory.update_memory(
                    order_placed=True,
                    order_id=order_result.order_id,
                    order_details={
                        "items": self.memory.missing_ingredients,
                        "total": order_result.total,
                        "email": decision.params.email
                    }
                )
                
                return ToolResponse(
                    content=[TextContent(
                        text=f"Order placed successfully! Order ID: {order_result.order_id}"
                    )]
                )

            elif decision.action == ActionType.SEND_EMAIL:
                if not self.memory.order_placed:
                    return ToolResponse(
                        content=[TextContent(
                            text="No order to send email for. Please place an order first."
                        )]
                    )
                
                # Format and send order confirmation email
                email_sent = self._send_order_email(
                    self.memory.order_details["email"],
                    self.memory.order_id,
                    self.memory.order_details["items"],
                    self.memory.order_details["total"]
                )
                
                if not email_sent:
                    return ToolResponse(
                        content=[TextContent(
                            text="Failed to send order confirmation email."
                        )]
                    )
                
                # Update memory
                self.memory.update_memory(email_sent=True)
                
                return ToolResponse(
                    content=[TextContent(
                        text="Order confirmation email sent successfully!"
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

        except (AttributeError, ValueError, json.JSONDecodeError, pydantic.ValidationError) as e:
            error_msg = f"Error executing {decision.action}: {str(e)}"
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
        except Exception as e:
            error_msg = f"Unexpected error in {decision.action}: {str(e)}"
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