from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AgentMemory(BaseModel):
    """Model representing agent's memory state"""
    dish_name: str = Field("", description="Name of the dish to cook")
    pantry_items: List[str] = Field(default_factory=list, description="Ingredients user has")
    required_ingredients: List[str] = Field(default_factory=list, description="Ingredients required for the dish")
    missing_ingredients: List[str] = Field(default_factory=list, description="Ingredients that need to be ordered")
    recipe_steps: List[str] = Field(default_factory=list, description="Steps to cook the dish")
    order_placed: bool = Field(False, description="Whether ingredients order has been placed")
    order_id: Optional[str] = Field(None, description="ID of the placed order")
    email_sent: bool = Field(False, description="Whether confirmation email was sent")
    user_email: str = Field("", description="User's email for notifications")

class MemoryLayer:
    def __init__(self, memory_file: str = "agent_memory.json", persist_to_disk: bool = True):
        logger.debug(f"Initializing MemoryLayer with memory file: {memory_file}")
        self.memory_file = memory_file
        self.persist_to_disk = persist_to_disk
        
        # Clear the memory file only during initialization
        if self.persist_to_disk:
            self._clear_memory_file()

        # Initialize fresh memory
        self.memory = AgentMemory()
        self.save_memory()  # Save initial clean state
        logger.info("Memory initialized to clean state")

    def load_memory(self) -> AgentMemory:
        """Load memory from disk or create new if doesn't exist"""
        if not self.persist_to_disk:
            logger.debug("Disk persistence disabled, using in-memory only")
            return AgentMemory()

        logger.info("Loading memory from disk")
        try:
            if os.path.exists(self.memory_file):
                logger.debug(f"Memory file exists: {self.memory_file}")
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded memory data: {data}")
                memory = AgentMemory(**data)
                logger.debug(f"Created AgentMemory model: {memory}")
                return memory
        except Exception as e:
            logger.error(f"Error loading memory: {e}", exc_info=True)
        
        logger.info("Creating new memory instance")
        return AgentMemory()

    def save_memory(self) -> None:
        """Save current memory state to disk if persistence is enabled"""
        if not self.persist_to_disk:
            logger.debug("Disk persistence disabled, skipping save")
            return

        logger.info("Saving memory to disk")
        try:
            memory_dict = self.memory.dict()
            logger.debug(f"Memory to save: {memory_dict}")
            with open(self.memory_file, 'w') as f:
                json.dump(memory_dict, f, indent=2)
            logger.debug("Memory saved successfully")
        except Exception as e:
            logger.error(f"Error saving memory: {e}", exc_info=True)

    def update_memory(self, **kwargs) -> None:
        """Update memory with new values"""
        logger.info("Updating memory")
        logger.debug(f"Update parameters: {kwargs}")
        for key, value in kwargs.items():
            if hasattr(self.memory, key):
                logger.debug(f"Updating {key} with value: {value}")
                setattr(self.memory, key, value)
            else:
                logger.warning(f"Attempted to update unknown memory attribute: {key}")
        self.save_memory()

    def get_memory(self) -> AgentMemory:
        """Get current memory state"""
        logger.debug(f"Getting current memory state: {self.memory}")
        return self.memory

    def get_context(self, perceived_input) -> dict:
        """Get context for decision making based on perceived input and memory"""
        logger.info("Getting context for decision making")
        logger.debug(f"Perceived input: {perceived_input}")
        
        # Only update fields that are present in the perceived input
        # while preserving other memory state
        logger.debug("Updating memory with perceived input while preserving state")
        if perceived_input.dish_name:
            self.update_memory(dish_name=perceived_input.dish_name)
        if perceived_input.pantry_items:
            self.update_memory(pantry_items=perceived_input.pantry_items)
        if perceived_input.user_email:
            self.update_memory(user_email=perceived_input.user_email)
        
        # Create context dictionary
        context = {
            "current_state": self.memory.dict(),
            "user_request": {
                "dish_name": perceived_input.dish_name,
                "pantry_items": perceived_input.pantry_items,
                "user_email": perceived_input.user_email
            }
        }
        logger.debug(f"Created context: {context}")
        return context

    def clear_memory(self) -> None:
        """Reset memory to initial state (in-memory only)"""
        logger.info("Resetting in-memory state")
        self.memory = AgentMemory()
        logger.debug("Memory reset to initial state")

    def _clear_memory_file(self) -> None:
        """Clear the memory file - should only be called during initialization"""
        logger.info("Clearing memory file")
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'w') as f:
                    json.dump({}, f)
                logger.debug("Memory file cleared")
        except Exception as e:
            logger.error(f"Error clearing memory file: {e}", exc_info=True) 