import logging
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# Global variable to track iteration
current_iteration = 0

def set_iteration(iteration_number):
    """Set current iteration number for logging"""
    global current_iteration
    current_iteration = iteration_number

# Define custom formatter with colors
class ColoredFormatter(logging.Formatter):
    """Custom formatter class that adds colors to log levels and includes iteration number"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Back.WHITE
    }

    MODULE_COLORS = {
        'perception': Fore.MAGENTA,
        'memory': Fore.BLUE,
        'action': Fore.YELLOW,
        'decision': Fore.GREEN,
        'main': Fore.WHITE,
        '__main__': Fore.WHITE
    }

    def format(self, record):
        # Save the original format
        orig_format = self._style._fmt

        # Add colors based on level
        levelname_color = self.COLORS.get(record.levelname, '')
        
        # Get module color
        module_name = record.name.split('.')[-1]  # Get the last part of the module name
        module_color = self.MODULE_COLORS.get(module_name, Fore.WHITE)
        
        # Format the module name with its color
        colored_module = f"{module_color}{module_name}{Style.RESET_ALL}"
        
        # Format the level name with its color
        colored_level = f"{levelname_color}{record.levelname}{Style.RESET_ALL}"
        
        # Include iteration number or 'Init' for pre-iteration logs
        if current_iteration == 0:
            iteration_info = f" [{Fore.CYAN}Init{Style.RESET_ALL}]"
        else:
            iteration_info = f" [{Fore.CYAN}Iter:{current_iteration + 1}{Style.RESET_ALL}]"
        
        # Set the format with colors and iteration number
        self._style._fmt = f'%(asctime)s{iteration_info} - {colored_module} - {colored_level} - %(message)s'

        # Call the original format method
        result = super().format(record)

        # Restore the original format
        self._style._fmt = orig_format

        return result

def setup_logging():
    """Setup logging configuration with colors"""
    # Create handler
    handler = logging.StreamHandler()
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Add formatter to handler
    handler.setFormatter(formatter)
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # Remove any existing handlers
    root_logger.handlers = []
    
    # Add our handler
    root_logger.addHandler(handler)
    
    # Set level
    root_logger.setLevel(logging.DEBUG) 