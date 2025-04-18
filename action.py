from typing import Any, Dict, List
import logging
from mcp import ClientSession
from decision import ActionType, Decision, ActionPlan
from memory import MemoryLayer
from pydantic import BaseModel
from models import (
    GetRecipeInput, GetRecipeOutput,
    CompareIngredientsInput, CompareIngredientsOutput,
    PlaceOrderInput, PlaceOrderOutput,
    SendEmailInput, SendEmailOutput,
    TextContent, ToolResponse
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class EmailFormatParams(BaseModel):
    """Model for email formatting parameters"""
    items: List[str]
    order_id: str

class ErrorResponse(BaseModel):
    """Model for standardized error responses"""
    error_type: str
    message: str
    details: Dict[str, Any] = {}

class ActionLayer:
    def __init__(self, recipe_session: ClientSession, delivery_session: ClientSession, gmail_session: ClientSession, memory_layer: MemoryLayer):
        logger.debug("Initializing ActionLayer")
        self.recipe_session = recipe_session
        self.delivery_session = delivery_session
        self.gmail_session = gmail_session
        self.memory = memory_layer
        logger.debug(f"ActionLayer initialized with memory: {self.memory}")

    async def execute(self, action_plan: ActionPlan) -> ToolResponse:
        """Execute the action plan from the decision layer"""
        logger.debug(f"Received action plan: {action_plan}")
        
        if action_plan.type == "function_call":
            logger.info(f"Processing function call: {action_plan.function}")
            # Convert function call format to Decision format
            decision = Decision(
                action=ActionType(action_plan.function),
                params=action_plan.parameters["input"],
                reasoning="Executing function call",
                fallback=action_plan.on_fail
            )
            logger.debug(f"Created decision object: {decision}")
            return await self.execute_action(decision)
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

    async def execute_action(self, decision: Decision) -> ToolResponse:
        """Execute the decided action using appropriate MCP tool"""
        logger.info(f"Executing action: {decision.action}")
        logger.debug(f"Action parameters: {decision.params}")
        
        try:
            if decision.action == ActionType.FETCH_RECIPE:
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
                        # First, get the text content from the MCP response
                        recipe_text = result.content[0].text
                        logger.debug(f"Raw recipe text: {recipe_text}")
                        
                        # If the response is a JSON string, parse it
                        try:
                            import json
                            if isinstance(recipe_text, str):
                                recipe_data = json.loads(recipe_text)
                                if isinstance(recipe_data, dict) and 'content' in recipe_data:
                                    recipe_text = recipe_data['content'][0]['text']
                        except json.JSONDecodeError:
                            # If not JSON, use the text as is
                            pass
                        
                        logger.debug(f"Processed recipe text: {recipe_text}")
                        
                        # Parse the recipe text to extract ingredients and steps
                        ingredients = []
                        steps = []
                        current_section = None
                        
                        for line in recipe_text.split('\n'):
                            line = line.strip()
                            if not line:  # Skip empty lines
                                continue
                            
                            logger.debug(f"Processing line: {line}")
                            
                            if 'Required ingredients:' in line:
                                current_section = 'ingredients'
                                logger.debug("Switched to ingredients section")
                                continue
                            elif 'Steps:' in line:
                                current_section = 'steps'
                                logger.debug("Switched to steps section")
                                continue
                            
                            if current_section == 'ingredients' and line.startswith('- '):
                                ingredient = line[2:].strip()
                                ingredients.append(ingredient)
                                logger.debug(f"Added ingredient: {ingredient}")
                            elif current_section == 'steps' and line[0].isdigit():
                                step = line.split('. ', 1)[1].strip()
                                steps.append(step)
                                logger.debug(f"Added step: {step}")
                        
                        logger.debug(f"Extracted ingredients: {ingredients}")
                        logger.debug(f"Extracted steps: {steps}")
                        
                        if not ingredients or not steps:
                            error_response = ErrorResponse(
                                error_type="ValidationError",
                                message="Failed to extract ingredients or steps from recipe",
                                details={"ingredients_found": bool(ingredients), "steps_found": bool(steps)}
                            )
                            raise ValueError(error_response.model_dump_json())
                        
                        # Create and validate the recipe output model
                        recipe_output = GetRecipeOutput.model_validate({
                            "required_ingredients": ingredients,
                            "recipe_steps": steps
                        })
                        
                        # Update memory with recipe information
                        self.memory.update_memory(
                            required_ingredients=recipe_output.required_ingredients,
                            recipe_steps=recipe_output.recipe_steps
                        )
                        
                        # Format the recipe text for display
                        display_text = "Recipe for Pasta Carbonara:\n\n"
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
                    except Exception as e:
                        error_response = ErrorResponse(
                            error_type="ParseError",
                            message=f"Error parsing recipe response: {str(e)}",
                            details={"raw_text": recipe_text if 'recipe_text' in locals() else None}
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

            elif decision.action == ActionType.CHECK_INGREDIENTS:
                # Parameters are already validated as CheckIngredientsParams
                input_model = CompareIngredientsInput(
                    required=decision.params.required,
                    available=decision.params.available
                )
                
                # Call tool with properly nested input
                result = await self.delivery_session.call_tool(
                    "compare_ingredients",
                    {"input": input_model.model_dump()}
                )
                
                # Parse the response using Pydantic model
                if hasattr(result, 'content') and result.content:
                    try:
                        comparison_output = CompareIngredientsOutput.model_validate_json(result.content[0].text)
                        
                        # Update memory with missing ingredients
                        self.memory.update_memory(missing_ingredients=comparison_output.missing_ingredients)
                        
                        # Format response for display
                        if comparison_output.missing_ingredients:
                            response_text = "Missing ingredients:\n" + "\n".join(f"- {ing}" for ing in comparison_output.missing_ingredients)
                        else:
                            response_text = "You have all the required ingredients!"
                        
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=response_text
                            )]
                        )
                    except Exception as e:
                        logger.error(f"Error parsing ingredients comparison: {e}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=f"Error comparing ingredients: {str(e)}"
                            )]
                        )
                
                return ToolResponse(
                    content=[TextContent(
                        type="text",
                        text="No ingredients comparison data received"
                    )]
                )

            elif decision.action == ActionType.PLACE_ORDER:
                # Parameters are already validated as PlaceOrderParams
                input_model = PlaceOrderInput(items=decision.params.items)
                
                # Call tool with properly nested input
                result = await self.delivery_session.call_tool(
                    "place_order",
                    {"input": input_model.model_dump()}
                )
                
                # Parse the response using Pydantic model
                if hasattr(result, 'content') and result.content:
                    try:
                        order_output = PlaceOrderOutput.model_validate_json(result.content[0].text)
                        
                        # Update memory with order details
                        self.memory.update_memory(
                            order_placed=order_output.order_placed,
                            order_id=order_output.order_id
                        )
                        
                        return ToolResponse(
                            content=[TextContent(
                                text=f"Order placed successfully!\nOrder ID: {order_output.order_id}\nTotal: ${order_output.total:.2f}"
                            )]
                        )
                    except Exception as e:
                        return ToolResponse(
                            content=[TextContent(
                                text=f"Error parsing order response: {str(e)}"
                            )]
                        )
                
                return ToolResponse(
                    content=[TextContent(
                        text="No order data received"
                    )]
                )

            elif decision.action == ActionType.SEND_EMAIL:
                # Parameters are already validated as SendEmailParams
                email_params = EmailFormatParams(
                    items=decision.params.items,
                    order_id=decision.params.order_id
                )
                
                # Format the email message using validated parameters
                message = self._format_order_email(
                    email_params.items,
                    email_params.order_id
                )
                
                # Create and validate input model
                input_model = SendEmailInput(
                    to=decision.params.email,
                    subject="Your Grocery Order Confirmation",
                    message=message
                )
                
                try:
                    # Call tool with properly nested input
                    result = await self.gmail_session.call_tool(
                        "send_email",
                        {"input": input_model.model_dump()}
                    )
                    
                    # Parse the response using Pydantic model
                    if hasattr(result, 'content') and result.content:
                        try:
                            email_output = SendEmailOutput.model_validate_json(result.content[0].text)
                            
                            # Update memory after successful email send
                            self.memory.update_memory(email_sent=True)
                            
                            return ToolResponse(
                                content=[TextContent(
                                    text=f"Email sent successfully to {input_model.to}\nMessage ID: {email_output.message_id}"
                                )]
                            )
                        except Exception as e:
                            error_response = ErrorResponse(
                                error_type="ValidationError",
                                message=f"Error parsing email response: {str(e)}",
                                details={"response_content": result.content[0].text if result.content else None}
                            )
                            raise ValueError(error_response.model_dump_json())
                    else:
                        error_response = ErrorResponse(
                            error_type="EmptyResponse",
                            message="No response content received from email server"
                        )
                        raise ValueError(error_response.model_dump_json())
                except Exception as e:
                    logger.error(f"Error sending email: {e}", exc_info=True)
                    # Ensure email_sent is False in memory if sending failed
                    self.memory.update_memory(email_sent=False)
                    return ToolResponse(
                        content=[TextContent(
                            text=str(e) if isinstance(e, ValueError) else ErrorResponse(
                                error_type="EmailError",
                                message=f"Failed to send email: {str(e)}"
                            ).model_dump_json()
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

        except Exception as e:
            logger.error(f"Error executing tool {decision.action.value}: {str(e)}", exc_info=True)
            return ToolResponse(
                content=[TextContent(
                    text=f"Error executing tool {decision.action.value}: {str(e)}"
                )]
            )

    def _format_order_email(self, items: list, order_id: str) -> str:
        """Format the order confirmation email"""
        items_list = "\n".join([f"- {item}" for item in items])
        return f"""
        Your grocery order has been placed!

        Order ID: {order_id}

        Items ordered:
        {items_list}

        Your items will be delivered soon. Happy cooking!
        """ 