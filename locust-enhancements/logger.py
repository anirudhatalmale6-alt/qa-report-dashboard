"""
Enhanced logging for the Locust framework.

Features:
- Per-script log files (e.g., logs/WSS_Retiredmem.log)
- Log rotation by size (5MB per file, keeps 3 backups)
- Separate log levels: DEBUG to file, INFO to console
- Thread-safe (works with multiple Locust users)
- Timestamped entries with thread ID for debugging concurrency

Usage:
    from framework.logger import framework_logger as logger
    logger.info("Login successful")
    logger.debug("Response cookies: %s", cookies)
    logger.error("Login failed for user %s", user_id)

    # Get a per-script logger:
    from framework.logger import get_script_logger
    script_logger = get_script_logger("WSS_Retiredmem")
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


# Log directory
LOG_DIR = "logs"


def get_framework_logger(name="framework", level=logging.DEBUG):
    """Create the main framework logger with file rotation and console output."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{name}.log")

    # Rotating file handler - DEBUG level, 5MB max, keep 3 backups
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler - INFO level (less noise in terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Format with thread name for debugging concurrency issues
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S"
    )

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_script_logger(script_name, level=logging.DEBUG):
    """
    Create a per-script logger that writes to its own log file.

    Args:
        script_name: Name of the Locust script (e.g., "WSS_Retiredmem")
                     Used as both the logger name and log filename.

    Returns:
        A configured logger instance.

    Example:
        logger = get_script_logger("WSS_Retiredmem")
        logger.info("Starting test for member %s", member_id)
    """
    logger_name = f"locust.{script_name}"
    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{script_name}.log")

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# Default framework logger instance
framework_logger = get_framework_logger("framework")
