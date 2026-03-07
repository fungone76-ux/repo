"""Logging configuration for Luna RPG v4.

V4.3: Centralized logging to replace print statements.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    module_name: str = "luna"
) -> logging.Logger:
    """Setup structured logging for Luna.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logs
        module_name: Root module name
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Format
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log debug to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


class LoggerMixin:
    """Mixin to add logging capability to any class."""
    
    def __init__(self) -> None:
        self._logger: Optional[logging.Logger] = None
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__module__)
        return self._logger
