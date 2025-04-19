import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from google import genai
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from perception import PerceptionLayer
from memory import MemoryLayer
from decision import DecisionLayer
from action import ActionLayer
from typing import Optional
from models import ActionPlan
import colorama
from colorama import Fore, Back, Style

# Configure logging
colorama.init()

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    COLORS = {
        'memory': Fore.LIGHTBLUE_EX,
        'action': Fore.LIGHTGREEN_EX,
        'decision': Fore.LIGHTMAGENTA_EX,
        'perception': Fore.LIGHTYELLOW_EX,
        'main': Fore.LIGHTCYAN_EX,  # Adding cyan color for main module
        '__main__': Fore.LIGHTCYAN_EX,  # Also handle __main__ module name
        'DEBUG': Fore.WHITE,
        'INFO': Fore.WHITE,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Back.RED + Fore.WHITE
    }

    def format(self, record):
        # Save original message
        original_msg = record.msg
        
        # Add color based on logger name
        if hasattr(record, 'name'):
            module_name = record.name.split('.')[-1]  # Get the last part of the logger name
            if module_name in self.COLORS:
                color = self.COLORS[module_name]
                # Add box formatting for specific types of messages
                if 'Current memory state' in str(record.msg):
                    record.msg = f"\n{color}{'='*100}\n{str(record.msg)}\n{'='*100}{Style.RESET_ALL}"
                elif any(x in str(record.msg) for x in ['Recipe Steps', 'Happy Cooking', 'Session Complete']):
                    record.msg = f"\n{color}{'*'*100}\n{str(record.msg)}\n{'*'*100}{Style.RESET_ALL}"
                elif 'Starting iteration' in str(record.msg) or 'Iteration complete' in str(record.msg):
                    record.msg = f"\n{color}{'~'*50} {str(record.msg)} {'~'*50}{Style.RESET_ALL}"
                else:
                    record.msg = f"{color}{str(record.msg)}{Style.RESET_ALL}"
        
        # Format the message
        formatted_msg = super().format(record)
        
        # Restore original message
        record.msg = original_msg
        
        return formatted_msg

# Create and configure the formatter
formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Remove any existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Create and configure console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# Get module logger
logger = logging.getLogger(__name__)

# Load environment variables
logger.info("Loading environment variables...")
start_time = time.time()
load_dotenv("./credentials/.env")
logger.info(f"Environment variables loaded in {time.time() - start_time:.2f}s")

# Initialize Gemini client
logger.info("Initializing Gemini client...")
start_time = time.time()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY not found in environment variables!")
client = genai.Client(api_key=api_key)
logger.info(f"Gemini client initialized in {time.time() - start_time:.2f}s")

async def generate_with_timeout(client, prompt, timeout=30):
    """Generate content with a timeout"""
    logger.info("Starting LLM generation...")
    start_time = time.time()
    try:
        await asyncio.sleep(2)  # Prevent throttling
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, 
                lambda: client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
            ),
            timeout=timeout
        )
        logger.info(f"LLM generation completed in {time.time() - start_time:.2f}s")
        return response
    except Exception as e:
        logger.error(f"Error in LLM generation after {time.time() - start_time:.2f}s: {e}")
        raise

class GroceryAssistant:
    def __init__(self):
        self._context_managers = []
        self.perception = PerceptionLayer()
        self.memory = MemoryLayer()
        self.decision = DecisionLayer()
        self.action = None  # Will be initialized in setup
        self.system_prompt = None
        self.recipe_session = None
        self.delivery_session = None
        self.gmail_session = None

    def create_system_prompt(self, tools_description: str) -> str:
        """Create the system prompt with available tools"""
        return f"""You are a cooking assistant that helps users prepare dishes by managing recipes and ingredients. You have access to various tools to look up recipes, check available ingredients in the user's pantry, place orders for missing ingredients, and send email notifications of orders placed for missing ingredients.

Available tools:
{tools_description}

Given the user's dish of choice, the ingredients available to them and their email, you must follow this EXACT sequence:
1. Get recipe details using get_recipe
2. IMMEDIATELY after getting recipe, compare available ingredients to those required by the recipe.
3. If any ingredients are missing, place order using place_order and follow with a confirmation email to the user.
4. Finally, display the recipe steps

You must respond with EXACTLY ONE valid JSON object in one of these formats (no additional text):

1. For reasoning and planning:
{{
  "type": "reasoning_block",
  "reasoning_type": "planning",
  "steps": [
    "Step 1: Get recipe details",
    "Step 2: Check available ingredients"
  ],
  "verify": "What to check before proceeding",
  "next": "What should happen next",
  "fallback_plan": "What to do if verification fails"
}}

2. For tool calls:
{{
  "type": "function_call",
  "function": "exact_tool_name",
  "parameters": {{
    "input": {{
      "param1": "value1",
      "param2": ["item1", "item2"]
    }}
  }},
  "on_fail": "fallback plan if the tool fails"
}}

3. For final answers:
{{
  "type": "final_answer",
  "value": "Here are your recipe steps... Happy cooking!"
}}

State Tracking Rules:
1. After get_recipe:
   - required_ingredients should be populated
   - recipe_steps should be populated
   - YOU MUST IMMEDIATELY CALL compare_ingredients

2. After compare_ingredients:
   - missing_ingredients should be populated
   - If empty, proceed to display recipe
   - If not empty, proceed to place order

3. After place_order:
   - order_id should be populated
   - order_placed should be True
   - Proceed to send email

4. After send_email:
   - email_sent should be True
   - Proceed to display recipe

5. Final recipe display:
   - Only show when either:
     a. No missing ingredients found, OR
     b. Order placed AND email sent

Example Flow:
1. Get Recipe:
{{
  "type": "function_call",
  "function": "get_recipe",
  "parameters": {{
    "input": {{
      "dish_name": "pasta carbonara"
    }}
  }}
}}

2. Compare Ingredients (MUST be called right after get_recipe):
{{
  "type": "function_call",
  "function": "compare_ingredients",
  "parameters": {{
    "input": {{
      "required": ["eggs", "pasta", "cheese"],
      "available": ["eggs"]
    }}
  }}
}}

3. If Missing Ingredients Found:
{{
  "type": "function_call",
  "function": "place_order",
  "parameters": {{
    "input": {{
      "items": ["pasta", "cheese"]
    }}
  }}
}}

4. Send Email:
{{
  "type": "function_call",
  "function": "send_email",
  "parameters": {{
    "input": {{
      "to": "user@example.com",
      "subject": "Order Confirmation",
      "message": "Your order #123 has been placed"
    }}
  }}
}}

5. Display Recipe:
{{
  "type": "final_answer",
  "value": "Now that all ingredients are secured, here are your cooking steps..."
}}

Remember:
- All responses must be valid JSON
- All string values must be in quotes
- Lists must use square brackets
- Parameters must be nested under "input" key
- Wait for each action's result before proceeding
- Check memory state before proceeding to next step
- ALWAYS compare ingredients immediately after getting recipe
- Only display recipe when ingredients are secured"""

    # async def setup(self):
    #     """Setup the assistant components"""
    #     setup_start = time.time()
    #     logger.info("Starting assistant setup...")

    #     # Create MCP server connections
    #     logger.info("Establishing connections to MCP servers...")

    #     recipe_params = StdioServerParameters(
    #         command="python",
    #         args=["./MCP_SERVERS/recipe_mcp_server.py"]
    #     )
    #     delivery_params = StdioServerParameters(
    #         command="python",
    #         args=["./MCP_SERVERS/delivery_mcp_server.py"]
    #     )
    #     gmail_params = StdioServerParameters(
    #         command="python",
    #         args=["./MCP_SERVERS/gmail_mcp_server.py", "--creds-file-path", "./credentials/credentials.json", "--token-path", "./credentials/token.json"]
    #     )

    #     # Create and store clients using context managers
    #     recipe_cm = stdio_client(recipe_params)
    #     delivery_cm = stdio_client(delivery_params)
    #     gmail_cm = stdio_client(gmail_params)
        
    #     self._context_managers.extend([recipe_cm, delivery_cm, gmail_cm])
        
    #     recipe_io = await recipe_cm.__aenter__()
    #     delivery_io = await delivery_cm.__aenter__()
    #     gmail_io = await gmail_cm.__aenter__()

    #     # Create sessions using context managers
    #     recipe_session_cm = ClientSession(*recipe_io)
    #     delivery_session_cm = ClientSession(*delivery_io)
    #     gmail_session_cm = ClientSession(*gmail_io)
        
    #     self._context_managers.extend([recipe_session_cm, delivery_session_cm, gmail_session_cm])
        
    #     self.recipe_session = await recipe_session_cm.__aenter__()
    #     self.delivery_session = await delivery_session_cm.__aenter__()
    #     self.gmail_session = await gmail_session_cm.__aenter__()

    #     logger.info("Sessions created, initializing...")
    #     await self.recipe_session.initialize()
    #     await self.delivery_session.initialize()
    #     await self.gmail_session.initialize()

    #     # Get available tools
    #     logger.info("Fetching available tools...")
    #     tools_start = time.time()
    #     recipe_tools = await self.recipe_session.list_tools()
    #     delivery_tools = await self.delivery_session.list_tools()
    #     gmail_tools = await self.gmail_session.list_tools()
    #     logger.info(f"Tools fetched in {time.time() - tools_start:.2f}s")

    #     # Create tools description
    #     logger.info("Creating tools description...")
    #     tools_desc = []
    #     for tools_result in [recipe_tools, delivery_tools, gmail_tools]:
    #         if hasattr(tools_result, 'tools'):
    #             tools = tools_result.tools
    #         else:
    #             tools = tools_result

    #         for tool in tools:
    #             try:
    #                 name = tool.name if hasattr(tool, 'name') else 'unnamed_tool'
    #                 desc = tool.description if hasattr(tool, 'description') else 'No description available'
                    
    #                 # Handle input schema
    #                 params_str = 'no parameters'
    #                 if hasattr(tool, 'inputSchema') and isinstance(tool.inputSchema, dict):
    #                     if 'properties' in tool.inputSchema:
    #                         param_details = []
    #                         for param_name, param_info in tool.inputSchema['properties'].items():
    #                             param_type = param_info.get('type', 'unknown')
    #                             param_details.append(f"{param_name}: {param_type}")
    #                         params_str = ', '.join(param_details)

    #                 tool_desc = f"{len(tools_desc) + 1}. {name}({params_str}) - {desc}"
    #                 tools_desc.append(tool_desc)
    #             except Exception as e:
    #                 logger.error(f"Error processing tool: {e}")
    #                 continue
        
    #     # Create system prompt
    #     logger.info("Creating system prompt...")
    #     self.system_prompt = self.create_system_prompt("\n".join(tools_desc))
        
    #     # Initialize action layer
    #     logger.info("Initializing action layer...")
    #     self.action = ActionLayer(self.recipe_session, self.delivery_session, self.gmail_session, self.memory)
        
    #     logger.info(f"Assistant setup completed in {time.time() - setup_start:.2f}s")

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Starting cleanup...")
        # Clean up in reverse order
        for cm in reversed(self._context_managers):
            try:
                if cm is not None:
                    logger.debug(f"Cleaning up context manager: {cm}")
                    await cm.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error during cleanup: {e}", exc_info=True)
                # Continue cleanup even if one fails
                continue
        self._context_managers.clear()
        logger.info("Cleanup completed")

    async def process_input(self, user_input: dict) -> dict:
        """Process user input through the cognitive layers"""
        logger.info("Starting input processing...")
        process_start = time.time()

        try:
            # Perception layer
            logger.info("Processing through perception layer...")
            perception_start = time.time()
            perceived_input = self.perception.parse_input(user_input)
            logger.info(f"Perception processing completed in {time.time() - perception_start:.2f}s")

            # Memory layer
            logger.info("Processing through memory layer...")
            memory_start = time.time()
            context = self.memory.get_context(perceived_input)
            logger.info(f"Memory processing completed in {time.time() - memory_start:.2f}s")

            # Decision layer
            logger.info("Processing through decision layer...")
            decision_start = time.time()
            action_plan = await self.decision.decide(context, self.system_prompt)
            logger.info(f"Decision processing completed in {time.time() - decision_start:.2f}s")

            # Action layer
            logger.info("Executing action plan...")
            action_start = time.time()
            result = await self.action.execute(action_plan)
            logger.info(f"Action execution completed in {time.time() - action_start:.2f}s")

            logger.info(f"Total input processing completed in {time.time() - process_start:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Error in input processing after {time.time() - process_start:.2f}s: {e}")
            raise

async def process_input(perception: PerceptionLayer, memory: MemoryLayer, decision: DecisionLayer, action: ActionLayer) -> Optional[str]:
    logger.debug("Starting process_input")
    
    # Get user input based on current memory state
    if not memory.memory.dish_name:  # Access dish_name through memory.memory
        dish_name = await perception.get_dish_name()
        if dish_name:
            memory.update_memory(dish_name=dish_name)
            logger.debug(f"Updated memory with dish name: {dish_name}")
    
    if memory.memory.dish_name and not memory.memory.required_ingredients:
        # Get recipe and ingredients
        recipe_decision = decision.decide_next_action(memory.memory)  # Remove await
        if recipe_decision:
            # Convert Decision to ActionPlan
            action_plan = ActionPlan(
                type="function_call",
                function=recipe_decision.action.value,
                parameters={"input": recipe_decision.params.model_dump()},
                on_fail=recipe_decision.fallback or f"Retry {recipe_decision.action.value} with modified parameters"
            )
            recipe_result = await action.execute(action_plan)
            if recipe_result and recipe_result.content:
                logger.debug(f"Recipe result: {recipe_result.content}")
                return recipe_result.content
    
    if memory.memory.required_ingredients and not memory.memory.pantry_items:
        # Get pantry items
        pantry_items = await perception.get_pantry_items(memory.memory.required_ingredients)
        if pantry_items:
            memory.update_memory(pantry_items=pantry_items)
            logger.debug(f"Updated memory with pantry items: {pantry_items}")
    
    if memory.memory.pantry_items and not memory.memory.missing_ingredients:
        # Compare ingredients
        compare_decision = decision.decide_next_action(memory.memory)  # Remove await
        if compare_decision:
            # Convert Decision to ActionPlan
            action_plan = ActionPlan(
                type="function_call",
                function=compare_decision.action.value,
                parameters={"input": compare_decision.params.model_dump()},
                on_fail=compare_decision.fallback or f"Retry {compare_decision.action.value} with modified parameters"
            )
            compare_result = await action.execute(action_plan)
            if compare_result and compare_result.content:
                logger.debug(f"Compare result: {compare_result.content}")
                return compare_result.content
    
    if memory.memory.missing_ingredients and not memory.memory.user_email:
        # Get user email
        email = await perception.get_email()
        if email:
            memory.update_memory(user_email=email)
            logger.debug(f"Updated memory with email: {email}")
    
    if memory.memory.user_email and memory.memory.missing_ingredients:
        # Place order
        order_decision = decision.decide_next_action(memory.memory)  # Remove await
        if order_decision:
            # Convert Decision to ActionPlan
            action_plan = ActionPlan(
                type="function_call",
                function=order_decision.action.value,
                parameters={"input": order_decision.params.model_dump()},
                on_fail=order_decision.fallback or f"Retry {order_decision.action.value} with modified parameters"
            )
            order_result = await action.execute(action_plan)
            if order_result and order_result.content:
                logger.debug(f"Order result: {order_result.content}")
                return order_result.content
    
    return None

async def main():
    logger.debug("Starting main")
    
    # Initialize components with MCP sessions
    recipe_params = StdioServerParameters(
        command="python",
        args=["./recipe_mcp_server.py"]
    )
    delivery_params = StdioServerParameters(
        command="python",
        args=["./delivery_mcp_server.py"]
    )
    gmail_params = StdioServerParameters(
        command="python",
        args=["./gmail_mcp_server.py", "--creds-file-path", "./credentials/credentials.json", "--token-path", "./credentials/token.json"]
    )

    async with stdio_client(recipe_params) as recipe_io, \
               stdio_client(delivery_params) as delivery_io, \
               stdio_client(gmail_params) as gmail_io:
        
        async with ClientSession(*recipe_io) as recipe_session, \
                   ClientSession(*delivery_io) as delivery_session, \
                   ClientSession(*gmail_io) as gmail_session:
            
            await recipe_session.initialize()
            await delivery_session.initialize()
            await gmail_session.initialize()
            
            memory = MemoryLayer()
            perception = PerceptionLayer()
            decision = DecisionLayer()  # Removed memory parameter
            action = ActionLayer(recipe_session, delivery_session, gmail_session, memory)
            
            iteration = 0
            max_iterations = 50
            
            while iteration < max_iterations:
                logger.debug("="*50 + f" Starting iteration {iteration+1} " + "="*50 + "\n")
                logger.debug(f"Current memory state: {memory}")
                
                result = await process_input(perception, memory, decision, action)
                if result:
                    print(result)
                logger.debug("="*50 + f"Iteration {iteration+1} complete " + "="*50 + "\n")

                # Check if we're done - wait for both order and email
                if memory.memory.user_email and memory.memory.order_placed and memory.memory.email_sent:
                    logger.debug("Order placed and email sent successfully")
                    # Display recipe in a clean format
                    print("\n" + "="*50 + " Recipe Steps " + "="*50)
                    print(f"\nRecipe for {memory.memory.dish_name.title()}:\n")
                    print("Ingredients you have:")
                    for item in memory.memory.pantry_items:
                        print(f"✓ {item}")
                    
                    print("\nIngredients ordered:")
                    for item in memory.memory.missing_ingredients:
                        print(f"→ {item}")
                    
                    print("\nCooking Steps:")
                    for i, step in enumerate(memory.memory.recipe_steps, 1):
                        print(f"{i}. {step}")
                    print("\n" + "="*50 + " Happy Cooking! " + "="*50 + "\n")
                    break
                
                iteration += 1
                await asyncio.sleep(0.1)  # Prevent throttling
            
            if iteration >= max_iterations:
                logger.warning("Reached maximum iterations without completing the task")

if __name__ == "__main__":
    asyncio.run(main()) 