from enum import Enum
from typing import Optional, Dict, Any, List, Union, Literal
from pydantic import BaseModel, Field
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

# Parameter models for each action type
class FetchRecipeParams(BaseModel):
    dish_name: str

class CheckIngredientsParams(BaseModel):
    required: List[str]
    available: List[str]

class PlaceOrderParams(BaseModel):
    items: List[str]

class SendEmailParams(BaseModel):
    email: str
    order_id: str
    items: List[str]

class DisplayRecipeParams(BaseModel):
    steps: List[str]

class InvalidInputParams(BaseModel):
    message: Optional[str] = None

ActionParams = Union[
    FetchRecipeParams,
    CheckIngredientsParams,
    PlaceOrderParams,
    SendEmailParams,
    DisplayRecipeParams,
    InvalidInputParams
]

class Decision(BaseModel):
    """Model representing a decision about next action"""
    action: ActionType
    params: ActionParams
    reasoning: str
    fallback: Optional[str] = None

    def get_parameters_dict(self) -> Dict[str, Any]:
        """Convert params to a dictionary format expected by the action layer"""
        if isinstance(self.params, (FetchRecipeParams, CheckIngredientsParams, 
                                  PlaceOrderParams, SendEmailParams, 
                                  DisplayRecipeParams, InvalidInputParams)):
            return self.params.model_dump()
        return {}

class ActionPlan(BaseModel):
    """Model representing the final action plan"""
    type: Literal["function_call"] = "function_call"
    function: str
    parameters: Dict[str, Dict[str, Any]]
    on_fail: str

class DecisionContext(BaseModel):
    """Model representing the input context for decision making"""
    current_state: Dict[str, Any]
    system_prompt: str

class DecisionLayer:
    def __init__(self):
        logger.debug("Initializing DecisionLayer")

    def decide_next_action(self, memory: AgentMemory) -> Decision:
        """Determine next action based on current memory state"""
        logger.info("Deciding next action")
        logger.debug(f"Current memory state: {memory}")
        
        # If dish name is empty or invalid
        if not memory.dish_name:
            logger.debug("No dish name provided")
            return Decision(
                action=ActionType.INVALID_INPUT,
                params=InvalidInputParams(message="No dish name provided"),
                reasoning="No dish name provided",
                fallback="Please provide the name of the dish you want to cook"
            )

        # If recipe not fetched yet
        if not memory.required_ingredients and not memory.recipe_steps:
            logger.debug("Recipe not fetched yet")
            decision = Decision(
                action=ActionType.FETCH_RECIPE,
                params=FetchRecipeParams(dish_name=memory.dish_name),
                reasoning="Need to fetch recipe and ingredients list"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If ingredients not compared yet
        if memory.required_ingredients and not memory.missing_ingredients:
            logger.debug("Ingredients comparison needed")
            decision = Decision(
                action=ActionType.CHECK_INGREDIENTS,
                params=CheckIngredientsParams(
                    required=memory.required_ingredients,
                    available=memory.pantry_items
                ),
                reasoning="Need to check which ingredients are missing"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If missing ingredients and order not placed
        if memory.missing_ingredients and not memory.order_placed:
            logger.debug("Order placement needed")
            decision = Decision(
                action=ActionType.PLACE_ORDER,
                params=PlaceOrderParams(items=memory.missing_ingredients),
                reasoning="Need to order missing ingredients"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If order placed but email not sent
        if memory.order_placed and not memory.email_sent and memory.order_id:
            logger.debug("Email confirmation needed")
            decision = Decision(
                action=ActionType.SEND_EMAIL,
                params=SendEmailParams(
                    email=memory.user_email,
                    order_id=memory.order_id,
                    items=memory.missing_ingredients
                ),
                reasoning="Need to send order confirmation email"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # If everything is ready, display recipe
        if memory.recipe_steps and memory.order_placed and memory.email_sent:
            logger.debug("Ready to display recipe")
            decision = Decision(
                action=ActionType.DISPLAY_RECIPE,
                params=DisplayRecipeParams(steps=memory.recipe_steps),
                reasoning="All ingredients secured, displaying recipe"
            )
            logger.debug(f"Created decision: {decision}")
            return decision

        # Fallback for unexpected states
        logger.warning("Unexpected state encountered")
        return Decision(
            action=ActionType.INVALID_INPUT,
            params=InvalidInputParams(message="Unexpected state"),
            reasoning="Unexpected state",
            fallback="Unable to determine next action. Please start over."
        )

    async def decide(self, context: dict, system_prompt: str) -> ActionPlan:
        """Make a decision based on context and system prompt"""
        logger.info("Making decision based on context and system prompt")
        
        try:
            # Validate input context
            decision_context = DecisionContext(
                current_state=context,
                system_prompt=system_prompt
            )
            logger.debug(f"Context: {decision_context}")
            
            # Extract memory from context - fix nested structure
            if "current_state" in context:
                current_state = context["current_state"]
            else:
                logger.error("Missing current_state in context")
                return ActionPlan(
                    function=ActionType.INVALID_INPUT.value,
                    parameters={"input": {"message": "Invalid context structure"}},
                    on_fail="Please try again with valid input"
                )
                
            logger.debug(f"Current state: {current_state}")
            
            try:
                memory = AgentMemory.model_validate(current_state)
                logger.debug(f"Created memory model: {memory}")
            except Exception as e:
                logger.error(f"Error validating memory state: {e}")
                return ActionPlan(
                    function=ActionType.INVALID_INPUT.value,
                    parameters={"input": {"message": f"Invalid memory state: {str(e)}"}},
                    on_fail="Please try again with valid input"
                )
            
            # Get next action decision
            decision = self.decide_next_action(memory)
            logger.debug(f"Next action decision: {decision}")
            
            # Convert decision to action plan
            action_plan = ActionPlan(
                function=decision.action.value,
                parameters={"input": decision.params.model_dump()},
                on_fail=decision.fallback or f"Retry {decision.action.value} with modified parameters"
            )
            logger.debug(f"Created action plan: {action_plan}")
            return action_plan
            
        except Exception as e:
            logger.error(f"Error in decision making: {str(e)}", exc_info=True)
            return ActionPlan(
                function=ActionType.INVALID_INPUT.value,
                parameters={"input": {"message": f"Error in decision making: {str(e)}"}},
                on_fail="Please try again with valid input"
            ) 