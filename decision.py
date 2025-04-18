from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel
from memory import AgentMemory
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ActionType(Enum):
    FETCH_RECIPE = "fetch_recipe"
    CHECK_INGREDIENTS = "check_ingredients"
    PLACE_ORDER = "place_order"
    SEND_EMAIL = "send_email"
    DISPLAY_RECIPE = "display_recipe"
    INVALID_INPUT = "invalid_input"

class Decision(BaseModel):
    """Model representing a decision about next action"""
    action: ActionType
    params: Dict[str, Any] = {}
    reasoning: str
    fallback: Optional[str] = None

class DecisionLayer:
    def __init__(self):
        logger.debug("Initializing DecisionLayer")

    def decide_next_action(self, memory) -> Decision:
        """Determine next action based on current memory state"""
        logger.info("Deciding next action")
        logger.debug(f"Current memory state: {memory}")
        
        # If dish name is empty or invalid
        if not memory.dish_name:
            logger.debug("No dish name provided")
            return Decision(
                action=ActionType.INVALID_INPUT,
                reasoning="No dish name provided",
                fallback="Please provide the name of the dish you want to cook"
            )

        # If recipe not fetched yet
        if not memory.required_ingredients and not memory.recipe_steps:
            logger.debug("Recipe not fetched yet")
            decision = Decision(
                action=ActionType.FETCH_RECIPE,
                params={"dish_name": memory.dish_name},
                reasoning="Need to fetch recipe and ingredients list"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If ingredients not compared yet
        if memory.required_ingredients and not memory.missing_ingredients:
            logger.debug("Ingredients comparison needed")
            decision = Decision(
                action=ActionType.CHECK_INGREDIENTS,
                params={
                    "required": memory.required_ingredients,
                    "available": memory.pantry_items
                },
                reasoning="Need to check which ingredients are missing"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If missing ingredients and order not placed
        if memory.missing_ingredients and not memory.order_placed:
            logger.debug("Order placement needed")
            decision = Decision(
                action=ActionType.PLACE_ORDER,
                params={"items": memory.missing_ingredients},
                reasoning="Need to order missing ingredients"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If order placed but email not sent
        if memory.order_placed and not memory.email_sent and memory.order_id:
            logger.debug("Email confirmation needed")
            decision = Decision(
                action=ActionType.SEND_EMAIL,
                params={
                    "email": memory.user_email,
                    "order_id": memory.order_id,
                    "items": memory.missing_ingredients
                },
                reasoning="Need to send order confirmation email"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If everything is ready, display recipe
        if memory.recipe_steps and memory.order_placed and memory.email_sent:
            logger.debug("Ready to display recipe")
            decision = Decision(
                action=ActionType.DISPLAY_RECIPE,
                params={"steps": memory.recipe_steps},
                reasoning="All ingredients secured, displaying recipe"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # Fallback for unexpected states
        logger.warning("Unexpected state encountered")
        return Decision(
            action=ActionType.INVALID_INPUT,
            reasoning="Unexpected state",
            fallback="Unable to determine next action. Please start over."
        )

    async def decide(self, context: dict, system_prompt: str) -> dict:
        """Make a decision based on context and system prompt"""
        logger.info("Making decision based on context and system prompt")
        logger.debug(f"Context: {context}")
        
        # Extract memory from context
        current_state = context["current_state"]
        logger.debug(f"Current state: {current_state}")
        
        memory = AgentMemory(**current_state)
        logger.debug(f"Created memory model: {memory}")
        
        # Get next action decision
        decision = self.decide_next_action(memory)
        logger.debug(f"Next action decision: {decision}")
        
        # Convert decision to format expected by action layer
        action_plan = {
            "type": "function_call",
            "function": decision.action.value,
            "parameters": {
                "input": decision.params
            },
            "on_fail": decision.fallback or f"Retry {decision.action.value} with modified parameters"
        }
        logger.debug(f"Created action plan: {action_plan}")
        return action_plan 