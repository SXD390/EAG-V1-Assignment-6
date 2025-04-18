from typing import Dict, Any, Optional
import logging
import json
import os
from models import AgentMemory, MemoryError, UserIntent

# Configure module logger
logger = logging.getLogger('memory')

class MemoryLayer:
    def __init__(self, memory_file: str = "MEMORY/agent_memory.json", persist_to_disk: bool = True):
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
                try:
                    memory = AgentMemory.model_validate(data)
                    logger.debug(f"Created AgentMemory model: {memory}")
                    return memory
                except Exception as e:
                    error = MemoryError(
                        error_type="ValidationError",
                        message="Failed to validate loaded memory data",
                        details={"data": data, "error": str(e)}
                    )
                    logger.error(error.model_dump_json())
                    return AgentMemory()
        except Exception as e:
            error = MemoryError(
                error_type="LoadError",
                message=f"Error loading memory: {str(e)}",
                details={"file": self.memory_file}
            )
            logger.error(error.model_dump_json())
        
        logger.info("Creating new memory instance")
        return AgentMemory()

    def save_memory(self) -> None:
        """Save current memory state to disk if persistence is enabled"""
        if not self.persist_to_disk:
            logger.debug("Disk persistence disabled, skipping save")
            return

        logger.info("Saving memory to disk")
        try:
            memory_dict = self.memory.model_dump()
            logger.debug(f"Memory to save: {memory_dict}")
            with open(self.memory_file, 'w') as f:
                json.dump(memory_dict, f, indent=2)
            logger.debug("Memory saved successfully")
        except Exception as e:
            error = MemoryError(
                error_type="SaveError",
                message=f"Error saving memory: {str(e)}",
                details={"file": self.memory_file}
            )
            logger.error(error.model_dump_json())

    def update_memory(self, **kwargs) -> None:
        """Update memory with new values"""
        logger.info("Updating memory")
        logger.debug(f"Update parameters: {kwargs}")
        try:
            # Create a dict of current values
            current_data = self.memory.model_dump()
            # Update with new values
            current_data.update(kwargs)
            # Validate entire state
            self.memory = AgentMemory.model_validate(current_data)
            self.save_memory()
        except Exception as e:
            error = MemoryError(
                error_type="UpdateError",
                message=f"Error updating memory: {str(e)}",
                details={"updates": kwargs}
            )
            logger.error(error.model_dump_json())
            raise ValueError(error.model_dump_json())

    def get_memory(self) -> AgentMemory:
        """Get current memory state"""
        logger.debug(f"Getting current memory state: {self.memory}")
        return self.memory

    def get_context(self, perceived_input) -> dict:
        """Get context for decision making based on perceived input and memory"""
        logger.info("Getting context for decision making")
        logger.debug(f"Perceived input: {perceived_input}")
        
        try:
            # Only update fields that are present in the perceived input
            # while preserving other memory state
            logger.debug("Updating memory with perceived input while preserving state")
            updates = {}
            if perceived_input.dish_name:
                updates["dish_name"] = perceived_input.dish_name
            if perceived_input.pantry_items:
                updates["pantry_items"] = perceived_input.pantry_items
            if perceived_input.user_email:
                updates["user_email"] = perceived_input.user_email
            
            if updates:
                self.update_memory(**updates)
            
            # Create context dictionary
            context = {
                "current_state": self.memory.model_dump(),
                "user_request": perceived_input.model_dump()
            }
            logger.debug(f"Created context: {context}")
            return context
            
        except Exception as e:
            error = MemoryError(
                error_type="ContextError",
                message=f"Error creating context: {str(e)}",
                details={"perceived_input": perceived_input.model_dump() if perceived_input else None}
            )
            logger.error(error.model_dump_json())
            raise ValueError(error.model_dump_json())

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
            error = MemoryError(
                error_type="ClearError",
                message=f"Error clearing memory file: {str(e)}",
                details={"file": self.memory_file}
            )
            logger.error(error.model_dump_json()) 