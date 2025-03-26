from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import random
import os
import time
import string
import platform
from pathlib import Path

def setup_chrome_driver(enable_cookies=True, user_data_dir=None, headless=False):
    """
    Configure ChromeDriver with enhanced anti-detection measures and session persistence.
    
    Args:
        enable_cookies: Whether to enable cookies persistence
        user_data_dir: Directory to store user data for session persistence
        headless: Whether to run in headless mode
        
    Returns:
        Configured Chrome WebDriver instance
    """
    options = webdriver.ChromeOptions()
    
    # Enhanced anti-detection measures
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-browser-side-navigation')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Additional webdriver v2 CDP options to avoid detection
    options.add_experimental_option('prefs', {
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False,
        'profile.default_content_setting_values.notifications': 2,
        'profile.managed_default_content_settings.images': 1,
        'profile.managed_default_content_settings.popups': 2
    })
    
    # Add additional language and timezone settings to appear more human-like
    options.add_argument('--lang=en-US,en;q=0.9')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    
    # Enable cookies and session persistence with enhanced settings
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
    
    # Enhanced user agent list with modern browsers
    user_agents = [
        # Modern Chrome
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        # Modern Firefox
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
        # Modern Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        # Modern Safari
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15'
    ]
    
    # Select a user agent based on the platform for better consistency
    current_platform = platform.system()
    if current_platform == 'Windows':
        platform_agents = [ua for ua in user_agents if 'Windows' in ua]
    elif current_platform == 'Darwin':
        platform_agents = [ua for ua in user_agents if 'Macintosh' in ua]
    elif current_platform == 'Linux':
        platform_agents = [ua for ua in user_agents if 'Linux' in ua]
    else:
        platform_agents = user_agents
    
    selected_agent = random.choice(platform_agents if platform_agents else user_agents)
    options.add_argument(f'user-agent={selected_agent}')
    
    # Headless mode with enhanced settings if requested
    if headless:
        options.add_argument('--headless=new')  # New headless implementation
        options.add_argument('--window-size=1920,1080')
        # Add specific headless settings to avoid detection
        options.add_argument('--disable-web-security')
    else:
        # For visible mode, use a randomized window size to appear more natural
        width = random.randint(1024, 1920)
        height = random.randint(768, 1080)
        options.add_argument(f'--window-size={width},{height}')
    
    # Additional performance and stability options
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-backgrounding-occluded-windows')
    
    # Create the driver using webdriver-manager for automatic ChromeDriver management
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error with ChromeDriverManager: {e}. Falling back to default Chrome webdriver.")
        driver = webdriver.Chrome(options=options)
    
    # Set page load and script timeouts to enhance stability
    driver.set_page_load_timeout(40)  # Increased timeout
    driver.set_script_timeout(40)  # Increased timeout
    
    # Execute enhanced anti-detection scripts
    driver.execute_script("""
    // Overwrite the 'webdriver' property
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    
    // Overwrite the navigator properties
    Object.defineProperties(navigator, {
        plugins: {
            get: () => {
                return [1, 2, 3, 4, 5];
            }
        },
        languages: {
            get: () => ['en-US', 'en', 'es']
        },
        deviceMemory: {
            get: () => 8  // Simulate 8GB RAM
        },
        hardwareConcurrency: {
            get: () => 8  // Simulate 8 cores
        }
    });
    
    // Create a fake notification permission state
    if ('permissions' in navigator) {
        navigator.permissions.query = (function(query) {
            return function(parameters) {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({state: Notification.permission, onchange: null});
                }
                return query.call(navigator.permissions, parameters);
            };
        })(navigator.permissions.query);
    }
    
    // Create a fake Chrome object
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {};
    }
    """)
    
    # Add a randomized fingerprint hash to make each browser instance unique
    fingerprint_hash = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    driver.execute_script(f"window.browserFingerprint = '{fingerprint_hash}';")
    
    # Small random delay to simulate human-like startup time
    time.sleep(random.uniform(0.5, 2.0))
    
    return driver
