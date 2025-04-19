from typing import Any, Dict
import logging
from mcp import ClientSession
from memory import MemoryLayer
from models import (
    GetRecipeInput, GetRecipeOutput,
    CompareIngredientsInput, CompareIngredientsOutput,
    PlaceOrderInput, PlaceOrderOutput,
    SendEmailInput, SendEmailOutput,
    TextContent, ToolResponse,
    ActionType, Decision, ActionPlan,
    EmailFormatParams, ErrorResponse
)
import pydantic
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
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

    async def compare_ingredients(self, input_model: CompareIngredientsInput) -> Dict:
        """Compare ingredients using the recipe MCP tool"""
        logger.info("Comparing ingredients")
        try:
            result = await self.recipe_session.call_tool(
                "compare_ingredients",
                {"input": input_model.model_dump()}
            )
            logger.debug(f"Raw comparison result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error comparing ingredients: {str(e)}", exc_info=True)
            raise

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

            elif decision.action == ActionType.CHECK_INGREDIENTS:
                # Parameters are already validated as CheckIngredientsParams
                input_model = CompareIngredientsInput(
                    required=decision.params.required,
                    available=decision.params.available
                )
                
                # Call tool with properly nested input
                result = await self.recipe_session.call_tool(
                    "compare_ingredients",
                    {"input": input_model.model_dump()}
                )
                
                # Parse the response using Pydantic model
                if hasattr(result, 'content') and result.content:
                    try:
                        # First parse: Get the inner JSON string
                        first_parse = json.loads(result.content[0].text)
                        
                        # Second parse: Parse the actual model data
                        inner_json = json.loads(first_parse['content'][0]['text'])
                        
                        # Validate against CompareIngredientsOutput model
                        comparison_output = CompareIngredientsOutput.model_validate(inner_json)
                        
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
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error: {je}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=f"Error decoding response: {str(je)}"
                            )]
                        )
                    except pydantic.ValidationError as ve:
                        logger.error(f"Validation error: {ve}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                type="text",
                                text=f"Error validating response: {str(ve)}"
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
                        # First parse: Get the inner JSON string
                        first_parse = json.loads(result.content[0].text)
                        
                        # Second parse: Parse the actual model data
                        inner_json = json.loads(first_parse['content'][0]['text'])
                        
                        # Validate against PlaceOrderOutput model
                        order_output = PlaceOrderOutput.model_validate(inner_json)
                        
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
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error: {je}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                text=f"Error decoding response: {str(je)}"
                            )]
                        )
                    except pydantic.ValidationError as ve:
                        logger.error(f"Validation error: {ve}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                text=f"Error validating response: {str(ve)}"
                            )]
                        )
                    except Exception as e:
                        logger.error(f"Error parsing order response: {e}", exc_info=True)
                        return ToolResponse(
                            content=[TextContent(
                                text=f"Error placing order: {str(e)}"
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
                            # Extract the inner JSON content (double-nested)
                            try:
                                # First parse to get the inner content
                                first_parse = json.loads(result.content[0].text)
                                
                                if isinstance(first_parse, dict) and 'content' in first_parse:
                                    # Get the text content from the inner structure
                                    inner_text = first_parse['content'][0]['text']
                                    # Parse the actual model data
                                    inner_json = json.loads(inner_text)
                                else:
                                    # If not nested, use the first parse
                                    inner_json = first_parse
                                
                                # Validate against SendEmailOutput model
                                email_output = SendEmailOutput.model_validate(inner_json)
                                
                                # Update memory after successful email send
                                self.memory.update_memory(email_sent=True)
                                
                                return ToolResponse(
                                    content=[TextContent(
                                        text=f"Email sent successfully to {input_model.to}\nMessage ID: {email_output.message_id}"
                                    )]
                                )
                            except json.JSONDecodeError as je:
                                raise
                            except pydantic.ValidationError as ve:
                                # If not a SendEmailOutput, try parsing as ErrorResponse
                                error_response = ErrorResponse.model_validate(inner_json)
                                raise ValueError(error_response.model_dump_json())
                                
                        except Exception as e:
                            logger.error(f"Error sending email: {e}", exc_info=True)
                            error_response = ErrorResponse(
                                error_type="ValidationError",
                                message=f"Error parsing email response: {str(e)}",
                                details={"response_content": result.content[0].text if result.content else None}
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
        </div>

        <!-- Items List -->
        <div style="background-color: #FFFFFF; border-radius: 10px; padding: 25px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px;">
            <h2 style="color: #2D3748; margin-top: 0; font-size: 20px; border-bottom: 2px solid #FF6B6B; padding-bottom: 10px;">Your Ingredients</h2>
            <ul style="list-style-type: none; padding-left: 0; color: #4A5568;">
                {items_list}
            </ul>
        </div>

        <!-- Delivery Info -->
        <div style="background-color: #FFFFFF; border-radius: 10px; padding: 25px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px;">
            <h2 style="color: #2D3748; margin-top: 0; font-size: 20px; border-bottom: 2px solid #FF6B6B; padding-bottom: 10px;">Delivery Information</h2>
            <p style="color: #4A5568; margin: 15px 0;">
                Your ingredients will be delivered soon. We'll make sure everything arrives fresh and ready for your cooking adventure!
            </p>
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