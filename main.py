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
from models import ActionPlan, LLMResponse
from log_config import setup_logging, set_iteration

# Configure logging using our custom configuration
setup_logging()
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
llm_client = genai.Client(api_key=api_key)
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
        self.llm_client = llm_client
        self.perception = None
        self.memory = None
        self.decision = None
        self.action = None
        self.system_prompt = None
        self.recipe_session = None
        self.delivery_session = None
        self.gmail_session = None

    def create_system_prompt(self, tools_description: str) -> str:
        """Create the system prompt with available tools"""
        return f"""You are an intelligent cooking assistant that helps users prepare dishes by managing recipes and ingredients. You have access to various tools and must follow structured reasoning and execution steps.

You must respond in exactly one of these formats:

For reasoning:
{{
  "type": "reasoning_block",
  "reasoning_type": "planning",
  "steps": ["step 1", "step 2"],
  "verify": "verification step",
  "next": "next action",
  "fallback_plan": "fallback plan"
}}

For tool calls:
{{
  "type": "function_call",
  "function": "exact_tool_name",
  "parameters": {{
    "param1": "value1"
  }},
  "on_fail": "fallback plan"
}}

For final answer:
{{
  "type": "final_answer",
  "value": "the final result"
}}

WHEN TO USE REASONING BLOCKS:
- At the beginning of a complex task
- After receiving a result that needs interpretation
- When selecting among multiple possible tools
- If a previous step failed

WHEN TO SKIP REASONING:
- For simple or deterministic tasks
- When the next action is obvious
- After a reasoning block has already planned the next function_call

FAILURE HANDLING RULES:
- Include fallback plans for reasoning blocks
- Include on_fail for function calls
- Return new reasoning block on unexpected failures

AVAILABLE TOOLS:
{tools_description}

RULES:
1. Return EXACTLY ONE valid JSON object
2. NO markdown or other formatting
3. NO text before or after the JSON
4. Wait for each action's result before proceeding
5. One action per step only
6. Verify results before proceeding
7. Include fallback plans
8. Keep track of state

Before responding, verify you are following all rules."""

    async def setup(self):
        """Setup the assistant components"""
        setup_start = time.time()
        logger.info("Starting assistant setup...")

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
        logger.debug(f"System prompt: {self.system_prompt}")
        # Initialize components
        logger.info("Initializing components...")
        self.perception = PerceptionLayer(self.llm_client)
        self.memory = MemoryLayer()
        self.decision = DecisionLayer(self.llm_client)
        self.action = ActionLayer(
            self.recipe_session,
            self.delivery_session,
            self.gmail_session,
            self.memory
        )
        
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
        # Reset memory file to empty dictionary
        try:
            with open('memory.json', 'w') as f:
                import json
                f.write(json.dumps({}))
            logger.debug("Memory file cleared")
        except Exception as e:
            logger.error(f"Error clearing memory file: {e}")
        logger.info("Cleanup completed")

    async def process_input(self, user_input: dict) -> dict:
        """Process user input through the cognitive layers"""
        logger.info("Starting input processing...")
        process_start = time.time()

        try:
            # Perception layer
            logger.info("Processing through perception layer...")
            perception_start = time.time()
            perceived_input = await self.perception.parse_input(user_input)
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
    logger.info("Starting main execution...")
    assistant = GroceryAssistant()
    
    try:
        # Setup assistant
        await assistant.setup()
        
        # Get initial user input
        print("\nEnter a word to start cooking: ", end='')
        user_word = input().strip()
        if not user_word:
            print("Error: Input cannot be empty")
            return

        # Create initial input
        user_input = {
            "dish_name": user_word,
            "pantry_items": None,
            "user_email": None
        }

        # Process input through cognitive cycle
        iteration = 0
        max_iterations = 20
        
        while iteration < max_iterations:
            logger.debug(f"\n=== Starting iteration {iteration + 1} ===\n")
            
            try:
                # Process through cognitive layers
                result = await assistant.process_input(user_input)
                
                # Handle result
                if result:
                    if hasattr(result, 'content'):
                        for content in result.content:
                            print(content.text)
                    else:
                        print(result)

                # Check if task is complete based on LLM response or recipe display
                memory = assistant.memory.get_memory()
                
                # Task is complete if:
                # 1. LLM returned a final_answer type response
                # 2. Last action was displaying the recipe
                # 3. Current state is one of the terminal states
                logger.debug(f"Checking completion status: {memory['current_state']}")
                
                # Define terminal states that indicate workflow completion
                terminal_states = [
                    "completed"  # Only completed is a final state
                ]
                
                if (hasattr(result, 'type') and result.type == "final_answer") or \
                   (memory["last_action"] == "display_recipe") or \
                   (memory["current_state"] in terminal_states):
                    logger.info(f"Task completed based on terminal state: {memory['current_state']}")
                    break

                # Get next user input if needed
                if memory["current_state"] == "awaiting_user_input":
                    print("\nPlease provide the requested information: ", end='')
                    user_response = input().strip()
                    user_input = {
                        "user_response": user_response
                    }
                    logger.debug(f"Got user input: {user_response}")
                else:
                    # Clear user input for next iteration
                    user_input = {}

            except Exception as e:
                logger.error(f"Error in iteration {iteration + 1}: {e}")
                print(f"An error occurred: {str(e)}")
                break

            iteration += 1
            # Update the iteration number in the log config
            set_iteration(iteration)
            await asyncio.sleep(0.1)  # Prevent throttling

        if iteration >= max_iterations:
            logger.warning("Reached maximum iterations without completing the task")
            print("\nTask took too long to complete. Please try again.")

    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}", exc_info=True)
        print(f"\nA fatal error occurred: {str(e)}")
    
    finally:
        # Cleanup
        await assistant.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 