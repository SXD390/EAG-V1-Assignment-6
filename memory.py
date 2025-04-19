from typing import Dict, Any, Optional, List
import logging
import json
import os
from models import AgentMemory, MemoryError, UserIntent
from pydantic import BaseModel, Field

# Get logger for this module
logger = logging.getLogger(__name__)

class MemoryLayer:
    def __init__(self, memory_file: str = "memory.json"):
        self.memory_file = memory_file
        self._memory = {
            # Recipe related
            "dish_name": None,
            "required_ingredients": [],
            "missing_ingredients": [],
            "available_ingredients": [],  # Added for storing pantry items
            "recipe_steps": [],
            
            # Order related
            "order_placed": False,
            "order_id": None,
            "order_details": {},  # Add order_details to store items and total
            "email_sent": False,
            "user_email": None,
            
            # State tracking
            "current_state": "initial",
            "last_action": None,
            "last_action_status": None,
            "retries": 0,
            "last_error": None
        }
        self._load_memory()

    def update_memory(self, **kwargs):
        """Update memory with new values"""
        logger.info("Updating memory")
        
        # Avoid logging full memory state - it gets verbose
        # Only log important updates
        important_keys = ["current_state", "last_action", "last_action_status", "order_placed", "email_sent"]
        important_updates = {k: v for k, v in kwargs.items() if k in important_keys}
        if important_updates:
            logger.debug(f"Important updates: {important_updates}")
        
        # Update memory with new values
        for key, value in kwargs.items():
            if key in self._memory:
                self._memory[key] = value
            else:
                logger.warning(f"Attempted to update unknown memory key: {key}")
        
        # Save updated memory
        self._save_memory()

    def get_memory(self) -> Dict[str, Any]:
        """Get current memory state"""
        return self._memory.copy()  # Return a copy to prevent accidental modifications

    # Commented out older version of get_context in favor of the newer implementation below
    # that handles perceived input and uses the newer memory model
    # def get_context(self) -> Dict[str, Any]:
    #     """Get context for decision making"""
    #     logger.info("Getting context for decision making")
    #     
    #     # Create context from current memory state
    #     context = {
    #         "current_state": {
    #             "state": self._memory["current_state"],
    #             "last_action": self._memory["last_action"],
    #             "last_action_status": self._memory["last_action_status"],
    #             "retries": self._memory["retries"],
    #             "last_error": self._memory["last_error"]
    #         },
    #         "task_progress": {
    #             "dish_name": self._memory["dish_name"],
    #             "recipe_obtained": bool(self._memory["recipe_steps"]),
    #             "ingredients_checked": bool(self._memory["missing_ingredients"]),
    #             "order_placed": self._memory["order_placed"],
    #             "email_sent": self._memory["email_sent"]
    #         },
    #         "recipe_details": {
    #             "required_ingredients": self._memory["required_ingredients"],
    #             "missing_ingredients": self._memory["missing_ingredients"],
    #             "recipe_steps": self._memory["recipe_steps"]
    #         },
    #         "order_details": {
    #             "order_id": self._memory["order_id"],
    #             "user_email": self._memory["user_email"]
    #         }
    #     }
    #     
    #     logger.debug(f"Created context: {context}")
    #     return context

    def _load_memory(self):
        """Load memory from file"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    saved_memory = json.load(f)
                    # Only update keys that exist in current memory
                    for key in self._memory.keys():
                        if key in saved_memory:
                            self._memory[key] = saved_memory[key]
        except Exception as e:
            logger.error(f"Error loading memory: {e}")

    def _save_memory(self):
        """Save memory to file"""
        logger.info("Saving memory to disk")
        try:
            logger.debug(f"Memory to save: {self._memory}")
            with open(self.memory_file, 'w') as f:
                json.dump(self._memory, f)
            logger.debug("Memory saved successfully")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")

    # Commented out as this version is not used. The class uses _load_memory instead
    # which works with self._memory dictionary directly
    # def load_memory(self) -> AgentMemory:
    #     """Load memory from disk or create new if doesn't exist"""
    #     if not self.persist_to_disk:
    #         logger.debug("Disk persistence disabled, using in-memory only")
    #         return AgentMemory()
    # 
    #     logger.info("Loading memory from disk")
    #     try:
    #         if os.path.exists(self.memory_file):
    #             logger.debug(f"Memory file exists: {self.memory_file}")
    #             with open(self.memory_file, 'r') as f:
    #                 data = json.load(f)
    #                 logger.debug(f"Loaded memory data: {data}")
    #             try:
    #                 memory = AgentMemory.model_validate(data)
    #                 logger.debug(f"Created AgentMemory model: {memory}")
    #                 return memory
    #             except Exception as e:
    #                 error = MemoryError(
    #                     error_type="ValidationError",
    #                     message="Failed to validate loaded memory data",
    #                     details={"data": data, "error": str(e)}
    #                 )
    #                 logger.error(error.model_dump_json())
    #                 return AgentMemory()
    #     except Exception as e:
    #         error = MemoryError(
    #             error_type="LoadError",
    #             message=f"Error loading memory: {str(e)}",
    #             details={"file": self.memory_file}
    #         )
    #         logger.error(error.model_dump_json())
    #     
    #     logger.info("Creating new memory instance")
    #     return AgentMemory()

    # Commented out as this version is not used. The class uses _save_memory instead
    # which works with self._memory dictionary directly
    # def save_memory(self) -> None:
    #     """Save current memory state to disk if persistence is enabled"""
    #     if not self.persist_to_disk:
    #         logger.debug("Disk persistence disabled, skipping save")
    #         return
    # 
    #     logger.info("Saving memory to disk")
    #     try:
    #         memory_dict = self.memory.model_dump()
    #         logger.debug(f"Memory to save: {memory_dict}")
    #         with open(self.memory_file, 'w') as f:
    #             json.dump(memory_dict, f, indent=2)
    #         logger.debug("Memory saved successfully")
    #     except Exception as e:
    #         error = MemoryError(
    #             error_type="SaveError",
    #             message=f"Error saving memory: {str(e)}",
    #             details={"file": self.memory_file}
    #         )
    #         logger.error(error.model_dump_json())

    def get_context(self, perceived_input: Optional[UserIntent] = None) -> dict:
        """Get context for decision making based on perceived input and memory"""
        logger.info("Getting context for decision making")
        logger.debug(f"Perceived input: {perceived_input}")
        
        try:
            # Update memory if new input is provided
            if perceived_input:
                updates = {}
                if perceived_input.dish_name:
                    updates["dish_name"] = perceived_input.dish_name
                if perceived_input.user_email:
                    updates["user_email"] = perceived_input.user_email
                
                if updates:
                    logger.debug(f"Updating memory with perceived input: {updates}")
                    self.update_memory(**updates)
            
            # Create context dictionary with metadata
            memory_state = self.get_memory()  # Get current memory state
            logger.debug(f"Building context from memory state: {memory_state}")
            
            context = {
                "current_state": {
                    "state": memory_state["current_state"],
                    "last_action": memory_state["last_action"],
                    "last_action_status": memory_state["last_action_status"],
                    "retries": memory_state["retries"],
                    "last_error": memory_state["last_error"]
                },
                "task_progress": {
                    "dish_name": memory_state["dish_name"],
                    "recipe_obtained": bool(memory_state["recipe_steps"]),
                    "ingredients_checked": bool(memory_state["missing_ingredients"]),
                    "order_placed": memory_state["order_placed"],
                    "email_sent": memory_state["email_sent"],
                    "user_email": memory_state["user_email"]
                },
                "recipe_details": {
                    "required_ingredients": memory_state["required_ingredients"],
                    "missing_ingredients": memory_state["missing_ingredients"],
                    "available_ingredients": memory_state["available_ingredients"],
                    "recipe_steps": memory_state["recipe_steps"]
                },
                "order_details": {
                    "order_id": memory_state["order_id"]
                }
            }
            
            logger.debug(f"Created context: {context}")
            return context
            
        except KeyError as ke:
            error = MemoryError(
                error_type="ContextError",
                message=f"Missing required memory key: {ke}",
                details={"memory_state": memory_state}
            )
            logger.error(error.model_dump_json())
            raise ValueError(error.model_dump_json())
        except Exception as e:
            error = MemoryError(
                error_type="ContextError",
                message=f"Error creating context: {str(e)}",
                details={"perceived_input": perceived_input.model_dump() if perceived_input else None}
            )
            logger.error(error.model_dump_json())
            raise ValueError(error.model_dump_json())

    def clear_memory(self) -> None:
        """Reset memory to initial state"""
        logger.info("Resetting memory state")
        self._memory = {
            "dish_name": None,
            "required_ingredients": [],
            "missing_ingredients": [],
            "available_ingredients": [],  # Added for storing pantry items
            "recipe_steps": [],
            "order_placed": False,
            "order_id": None,
            "order_details": {},  # Add order_details to stay consistent
            "email_sent": False,
            "user_email": None,
            "current_state": "initial",
            "last_action": None,
            "last_action_status": None,
            "retries": 0,
            "last_error": None
        }
        self._save_memory()
        logger.debug("Memory reset to initial state")

    # Commented out as clear_memory() above provides a more complete implementation
    # def _clear_memory_file(self) -> None:
    #     """Clear the memory file - should only be called during initialization"""
    #     logger.info("Clearing memory file")
    #     try:
    #         if os.path.exists(self.memory_file):
    #             with open(self.memory_file, 'w') as f:
    #                 json.dump({}, f)
    #             logger.debug("Memory file cleared")
    #     except Exception as e:
    #         error = MemoryError(
    #             error_type="ClearError",
    #             message=f"Error clearing memory file: {str(e)}",
    #             details={"file": self.memory_file}
    #         )
    #         logger.error(error.model_dump_json()) 