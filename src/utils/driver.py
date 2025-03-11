from selenium import webdriver
import random
import os
import time
from pathlib import Path

def setup_chrome_driver(enable_cookies=True, user_data_dir=None, headless=False):
    """
    Configure ChromeDriver with anti-detection measures and session persistence.
    
    Args:
        enable_cookies: Whether to enable cookies persistence
        user_data_dir: Directory to store user data for session persistence
        headless: Whether to run in headless mode
        
    Returns:
        Configured Chrome WebDriver instance
    """
    options = webdriver.ChromeOptions()
    
    # Add anti-detection measures
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-browser-side-navigation')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Enable cookies and session persistence
    if enable_cookies:
        # Don't clear cookies between sessions
        options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
        options.add_argument('--profile-directory=Default')
        
        # Set up user data directory for session persistence
        if user_data_dir:
            data_dir = user_data_dir
        else:
            # Default to a directory in the project
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'chrome_data')
        
        # Create directory if it doesn't exist
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        
        options.add_argument(f'--user-data-dir={data_dir}')
    
    # Add random user agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    # Headless mode if requested
    if headless:
        options.add_argument('--headless')
        options.add_argument('--window-size=1920,1080')  # Set window size for headless mode
    
    # Additional options for better performance and stability
    options.add_argument('--start-maximized')  # Start maximized
    options.add_argument('--disable-extensions')  # Disable extensions
    options.add_argument('--disable-popup-blocking')  # Disable popup blocking
    options.add_argument('--disable-notifications')  # Disable notifications
    
    # Create and return the driver
    driver = webdriver.Chrome(options=options)
    
    # Set page load timeout to 30 seconds
    driver.set_page_load_timeout(30)
    
    # Set script timeout to 30 seconds
    driver.set_script_timeout(30)
    
    # Execute anti-detection script
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver
