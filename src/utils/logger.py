from colorama import init, Fore, Style
import logging
import os
import sys
from datetime import datetime

# Initialize colorama for colored console output
init()

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels in console output"""
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        record.asctime = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        return super().format(record)

def ensure_log_directory():
    """Ensure the logs directory exists."""
    log_dir = 'data/logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

def setup_logger():
    """
    Set up and configure a logging system with colored console output
    and plain-text file logging for errors, successes, and results.
    """
    ensure_log_directory()

    # Create root logger
    logger = logging.getLogger('SocialScraper')
    logger.setLevel(logging.DEBUG)

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    # File handlers for different log types
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # General debug/info log (detailed operations)
    debug_handler = logging.FileHandler(os.path.join('data/logs', f'debug_{timestamp}.log'))
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(debug_handler)

    # Error log (critical issues)
    error_handler = logging.FileHandler(os.path.join('data/logs', f'error_{timestamp}.log'))
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(error_handler)

    # Success log (high-level success messages)
    success_logger = logging.getLogger('SuccessLog')
    success_logger.setLevel(logging.INFO)
    success_handler = logging.FileHandler(os.path.join('data/logs', f'success_{timestamp}.log'))
    success_handler.setLevel(logging.INFO)
    success_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    success_logger.addHandler(success_handler)

    # Results log (plain-text scraped data, simple format)
    results_logger = logging.getLogger('ScraperResults')
    results_logger.setLevel(logging.INFO)
    results_handler = logging.FileHandler(os.path.join('data/logs', f'results_{timestamp}.log'))
    results_handler.setLevel(logging.INFO)
    results_handler.setFormatter(logging.Formatter('%(asctime)s - Athlete: %(message)s'))
    results_logger.addHandler(results_handler)

    # Prevent duplicate handlers
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            continue
        logger.removeHandler(handler)
    for handler in success_logger.handlers[:]:
        success_logger.removeHandler(handler)
    for handler in results_logger.handlers[:]:
        results_logger.removeHandler(handler)

    return logger, success_logger, results_logger