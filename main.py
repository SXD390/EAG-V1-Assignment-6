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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
logger.info("Loading environment variables...")
start_time = time.time()
load_dotenv()
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
        self.perception = PerceptionLayer()
        self.memory = MemoryLayer(persist_to_disk=False)  # Use in-memory only
        self.decision = DecisionLayer()
        self.action = None
        self.system_prompt = None
        self.recipe_session = None
        self.delivery_session = None
        self.gmail_session = None
        self._context_managers = []

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

    async def setup(self):
        """Initialize MCP servers"""
        logger.info("Starting assistant setup...")
        setup_start = time.time()

        # Create MCP server connections
        logger.info("Establishing connections to MCP servers...")
        
        recipe_params = StdioServerParameters(
            command="python",
            args=["recipe_mcp_server.py"]
        )
        delivery_params = StdioServerParameters(
            command="python",
            args=["delivery_mcp_server.py"]
        )
        gmail_params = StdioServerParameters(
            command="python",
            args=["gmail_mcp_server.py", "--creds-file-path", "credentials.json", "--token-path", "token.json"]
        )

        # Create and store clients using context managers
        recipe_cm = stdio_client(recipe_params)
        delivery_cm = stdio_client(delivery_params)
        gmail_cm = stdio_client(gmail_params)
        
        self._context_managers.extend([recipe_cm, delivery_cm, gmail_cm])
        
        recipe_io = await recipe_cm.__aenter__()
        delivery_io = await delivery_cm.__aenter__()
        gmail_io = await gmail_cm.__aenter__()

        # Create sessions using context managers
        recipe_session_cm = ClientSession(*recipe_io)
        delivery_session_cm = ClientSession(*delivery_io)
        gmail_session_cm = ClientSession(*gmail_io)
        
        self._context_managers.extend([recipe_session_cm, delivery_session_cm, gmail_session_cm])
        
        self.recipe_session = await recipe_session_cm.__aenter__()
        self.delivery_session = await delivery_session_cm.__aenter__()
        self.gmail_session = await gmail_session_cm.__aenter__()

        logger.info("Sessions created, initializing...")
        await self.recipe_session.initialize()
        await self.delivery_session.initialize()
        await self.gmail_session.initialize()

        # Get available tools
        logger.info("Fetching available tools...")
        tools_start = time.time()
        recipe_tools = await self.recipe_session.list_tools()
        delivery_tools = await self.delivery_session.list_tools()
        gmail_tools = await self.gmail_session.list_tools()
        logger.info(f"Tools fetched in {time.time() - tools_start:.2f}s")

        # Create tools description
        logger.info("Creating tools description...")
        tools_desc = []
        for tools_result in [recipe_tools, delivery_tools, gmail_tools]:
            if hasattr(tools_result, 'tools'):
                tools = tools_result.tools
            else:
                tools = tools_result

            for tool in tools:
                try:
                    name = tool.name if hasattr(tool, 'name') else 'unnamed_tool'
                    desc = tool.description if hasattr(tool, 'description') else 'No description available'
                    
                    # Handle input schema
                    params_str = 'no parameters'
                    if hasattr(tool, 'inputSchema') and isinstance(tool.inputSchema, dict):
                        if 'properties' in tool.inputSchema:
                            param_details = []
                            for param_name, param_info in tool.inputSchema['properties'].items():
                                param_type = param_info.get('type', 'unknown')
                                param_details.append(f"{param_name}: {param_type}")
                            params_str = ', '.join(param_details)

                    tool_desc = f"{len(tools_desc) + 1}. {name}({params_str}) - {desc}"
                    tools_desc.append(tool_desc)
                except Exception as e:
                    logger.error(f"Error processing tool: {e}")
                    continue
        
        # Create system prompt
        logger.info("Creating system prompt...")
        self.system_prompt = self.create_system_prompt("\n".join(tools_desc))
        
        # Initialize action layer
        logger.info("Initializing action layer...")
        self.action = ActionLayer(self.recipe_session, self.delivery_session, self.gmail_session, self.memory)
        
        logger.info(f"Assistant setup completed in {time.time() - setup_start:.2f}s")

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

async def main():
    """Main entry point"""
    logger.info("Starting main application...")
    main_start = time.time()
    assistant = None
    max_iterations = 50  # Cap the number of iterations
    current_iteration = 0  # Track current iteration

    try:
        # Initialize assistant
        assistant = GroceryAssistant()
        logger.info("Setting up assistant...")
        await assistant.setup()
        logger.info("Assistant setup complete")

        # Initial user input
        user_input = {
            "dish_name": "pasta carbonara",
            "pantry_items": ["eggs"],
            "user_email": "sudarshanravi13@gmail.com"
        }
        
        # Process input until recipe is ready to be displayed or max iterations reached
        while current_iteration < max_iterations:
            print(f"\n{'='*20} Iteration {current_iteration + 1} {'='*20}")
            logger.info(f"Processing step {current_iteration + 1}/{max_iterations}...")
            result = await assistant.process_input(user_input)
            print(result)
            
            # Get current memory state
            memory = assistant.memory.get_memory()
            logger.debug(f"Current memory state: {memory}")
            
            # Check if we have completed all necessary steps
            if memory.recipe_steps:  # We have the recipe
                if memory.required_ingredients and not memory.missing_ingredients:
                    # We have required ingredients but haven't compared yet
                    logger.info("Required ingredients found, proceeding with comparison")
                elif memory.missing_ingredients:
                    if memory.order_placed and memory.email_sent:
                        # We have missing ingredients but order is placed and email sent
                        logger.info("Order placed and confirmed, recipe ready to display")
                        break
                    else:
                        # Still need to place order or send email
                        logger.info("Processing order and email steps")
                elif memory.required_ingredients and memory.missing_ingredients == []:
                    # We've done the comparison and found no missing ingredients
                    logger.info("No missing ingredients after comparison, recipe ready to display")
                    break
            
            # Increment iteration counter
            current_iteration += 1
            if current_iteration >= max_iterations:
                logger.warning(f"Reached maximum iterations ({max_iterations}), stopping execution")
                break
            
            print(f"{'='*20} End of iteration {current_iteration} {'='*20}\n")
            # Add a small delay to prevent throttling
            await asyncio.sleep(1)

        logger.info(f"Main application completed in {time.time() - main_start:.2f}s")

    except Exception as e:
        logger.error(f"Error in main application after {time.time() - main_start:.2f}s: {e}", exc_info=True)
    finally:
        if assistant:
            try:
                await assistant.cleanup()
            except Exception as e:
                logger.error(f"Error during final cleanup: {e}", exc_info=True)
                # Don't re-raise the error since we're in cleanup

if __name__ == "__main__":
    asyncio.run(main()) 