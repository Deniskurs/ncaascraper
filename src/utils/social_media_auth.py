import os
import time
import random
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

class SocialMediaAuth:
    """
    Handles authentication for various social media platforms.
    Supports Twitter, Facebook, and Instagram.
    """
    
    def __init__(self, driver, logger, screenshot_dir=None):
        """
        Initialize the authentication module.
        
        Args:
            driver: Selenium WebDriver instance
            logger: Logger instance for logging
            screenshot_dir: Directory to save authentication screenshots (optional)
        """
        self.driver = driver
        self.logger = logger
        
        # Set up screenshot directory
        if screenshot_dir:
            self.screenshot_dir = screenshot_dir
        else:
            self.screenshot_dir = os.path.join("data", "screenshots", "auth")
            
        # Create screenshot directory if it doesn't exist
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
            
        # Load credentials from environment variables
        self.credentials = {
            'facebook': {
                'email': os.environ.get('FACEBOOK_EMAIL'),
                'password': os.environ.get('FACEBOOK_PASSWORD')
            },
            'instagram': {
                'username': os.environ.get('INSTAGRAM_USERNAME'),
                'password': os.environ.get('INSTAGRAM_PASSWORD')
            },
            'twitter': {
                'email': os.environ.get('TWITTER_EMAIL'),
                'username': os.environ.get('TWITTER_USERNAME'),
                'password': os.environ.get('TWITTER_PASSWORD')
            }
        }
        
        # Track authentication status
        self.auth_status = {
            'facebook': False,
            'instagram': False,
            'twitter': False
        }
    
    def authenticate_all(self, platforms=None):
        """
        Authenticate with all specified social media platforms.
        
        Args:
            platforms: List of platforms to authenticate with. 
                      If None, authenticates with all supported platforms.
        
        Returns:
            Dictionary with authentication results for each platform
        """
        if platforms is None:
            platforms = ['twitter', 'facebook', 'instagram']
            
        results = {}
        
        for platform in platforms:
            # Handle cookie consent before attempting login
            self.handle_cookie_consent(platform)
            
            if platform.lower() == 'twitter':
                success, message = self.login_twitter()
            elif platform.lower() == 'facebook':
                success, message = self.login_facebook()
            elif platform.lower() == 'instagram':
                success, message = self.login_instagram()
            else:
                success, message = False, f"Unsupported platform: {platform}"
                
            results[platform] = {
                'success': success,
                'message': message
            }
            
            # Update authentication status
            self.auth_status[platform.lower()] = success
            
            # Verify login was successful with extended check
            if success:
                is_logged_in = self._check_login_status(platform.lower(), extended_check=True)
                if not is_logged_in:
                    self.logger.warning(f"Login reported success but verification failed for {platform}")
                    results[platform]['success'] = False
                    results[platform]['message'] = "Login verification failed"
                    self.auth_status[platform.lower()] = False
            
            # Add random delay between logins
            if platform != platforms[-1]:
                time.sleep(random.uniform(2.0, 4.0))
                
        return results
        
    def ensure_login(self, platforms=None):
        """
        Ensure login sessions are active, and re-login if necessary
        
        Args:
            platforms: List of platforms to check/ensure login
            
        Returns:
            Dictionary with login status for each platform
        """
        if platforms is None:
            platforms = ['twitter', 'facebook', 'instagram']
            
        results = {}
        
        for platform in platforms:
            is_logged_in = self._check_login_status(platform)
            if is_logged_in:
                self.logger.info(f"Already logged in to {platform}")
                results[platform] = {"success": True, "message": "Already logged in"}
                self.auth_status[platform] = True
            else:
                self.logger.info(f"Not logged in to {platform}, attempting login")
                
                # Navigate to platform homepage to check cookie consent
                if platform == 'twitter':
                    self.driver.get("https://twitter.com/")
                elif platform == 'facebook':
                    self.driver.get("https://www.facebook.com/")
                elif platform == 'instagram':
                    self.driver.get("https://www.instagram.com/")
                
                # Handle cookie consent before login attempt
                self.handle_cookie_consent(platform)
                
                # Attempt login
                if platform.lower() == 'twitter':
                    success, message = self.login_twitter()
                elif platform.lower() == 'facebook':
                    success, message = self.login_facebook()
                elif platform.lower() == 'instagram':
                    success, message = self.login_instagram()
                else:
                    success, message = False, f"Unsupported platform: {platform}"
                    
                results[platform] = {"success": success, "message": message}
                self.auth_status[platform] = success
                
                # Verify login was successful
                if success:
                    is_logged_in = self._check_login_status(platform, extended_check=True)
                    if not is_logged_in:
                        self.logger.warning(f"Login reported success but verification failed for {platform}")
                        results[platform] = {"success": False, "message": "Login verification failed"}
                        self.auth_status[platform] = False
            
            # Add random delay between platform checks
            if platform != platforms[-1]:
                time.sleep(random.uniform(2.0, 4.0))
                    
        return results
    
    def login_twitter(self, max_retries=2):
        """
        Log in to Twitter using credentials from environment variables.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, message)
        """
        platform = 'twitter'
        self.logger.info("Attempting to log in to Twitter...")
        
        # Check if credentials are available
        if not self.credentials[platform]['email'] or not self.credentials[platform]['password']:
            return False, "Twitter credentials not found in environment variables"
            
        # Get credentials
        email = self.credentials[platform]['email']
        username = self.credentials[platform]['username']
        password = self.credentials[platform]['password']
        
        retry_count = 0
        while retry_count <= max_retries:
            try:
                # Navigate to Twitter login page
                self.driver.get("https://twitter.com/login")
                time.sleep(3)  # Wait for page to load
                
                # Check if we're already logged in
                if self._is_twitter_logged_in():
                    self.logger.info("Already logged in to Twitter")
                    return True, "Already logged in"
                
                # Wait for the username/email field
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='text']"))
                )
                
                # Enter email or username
                username_field.clear()
                username_field.send_keys(email)
                
                # Find and click the Next button
                next_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
                )
                next_button.click()
                time.sleep(2)
                
                # Check if we need to enter username (Twitter sometimes asks for this after email)
                try:
                    username_challenge = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='ocfEnterTextTextInput']"))
                    )
                    username_challenge.clear()
                    username_challenge.send_keys(username)
                    
                    # Click Next again
                    next_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
                    )
                    next_button.click()
                    time.sleep(2)
                except TimeoutException:
                    # No username challenge, continue with password
                    pass
                
                # Enter password
                password_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
                )
                password_field.clear()
                password_field.send_keys(password)
                
                # Click login button
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='Log in']"))
                )
                login_button.click()
                
                # Wait for home page to load
                time.sleep(5)
                
                # Verify login success
                if self._is_twitter_logged_in():
                    self.logger.info("Successfully logged in to Twitter")
                    return True, "Login successful"
                else:
                    # Take screenshot for debugging
                    self._take_auth_screenshot("twitter_failed")
                    
                    # Check for specific error messages
                    if "Verify your identity" in self.driver.page_source:
                        self.logger.warning("Twitter login requires identity verification")
                        return False, "Identity verification required"
                    
                    retry_count += 1
                    if retry_count <= max_retries:
                        self.logger.warning(f"Twitter login failed, retrying ({retry_count}/{max_retries})...")
                        time.sleep(3)
                    else:
                        self.logger.error("Twitter login failed after maximum retries")
                        return False, "Login failed after maximum retries"
            
            except TimeoutException as e:
                self._take_auth_screenshot("twitter_timeout")
                self.logger.error(f"Timeout during Twitter login: {str(e)}")
                retry_count += 1
                if retry_count <= max_retries:
                    self.logger.warning(f"Retrying Twitter login ({retry_count}/{max_retries})...")
                    time.sleep(3)
                else:
                    return False, f"Timeout during login: {str(e)}"
                    
            except Exception as e:
                self._take_auth_screenshot("twitter_error")
                self.logger.error(f"Error during Twitter login: {str(e)}")
                return False, f"Error during login: {str(e)}"
        
        return False, "Login failed after maximum retries"
    
    def login_facebook(self, max_retries=2):
        """
        Log in to Facebook using credentials from environment variables.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, message)
        """
        platform = 'facebook'
        self.logger.info("Attempting to log in to Facebook...")
        
        # Check if credentials are available
        if not self.credentials[platform]['email'] or not self.credentials[platform]['password']:
            return False, "Facebook credentials not found in environment variables"
            
        # Get credentials
        email = self.credentials[platform]['email']
        password = self.credentials[platform]['password']
        
        retry_count = 0
        while retry_count <= max_retries:
            try:
                # Navigate to Facebook login page
                self.driver.get("https://www.facebook.com/")
                time.sleep(3)  # Wait for page to load
                
                # Check if we're already logged in
                if self._is_facebook_logged_in():
                    self.logger.info("Already logged in to Facebook")
                    return True, "Already logged in"
                
                # Handle cookie consent
                self.handle_cookie_consent('facebook')
                
                # Enter email
                email_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )
                email_field.clear()
                email_field.send_keys(email)
                
                # Enter password
                password_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "pass"))
                )
                password_field.clear()
                password_field.send_keys(password)
                
                # Click login button
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.NAME, "login"))
                )
                login_button.click()
                
                # Wait for home page to load
                time.sleep(5)
                
                # Verify login success
                if self._is_facebook_logged_in():
                    self.logger.info("Successfully logged in to Facebook")
                    return True, "Login successful"
                else:
                    # Take screenshot for debugging
                    self._take_auth_screenshot("facebook_failed")
                    
                    # Check for specific error messages
                    if "Verify Your Identity" in self.driver.page_source or "security check" in self.driver.page_source.lower():
                        self.logger.warning("Facebook login requires identity verification")
                        return False, "Identity verification required"
                    
                    retry_count += 1
                    if retry_count <= max_retries:
                        self.logger.warning(f"Facebook login failed, retrying ({retry_count}/{max_retries})...")
                        time.sleep(3)
                    else:
                        self.logger.error("Facebook login failed after maximum retries")
                        return False, "Login failed after maximum retries"
            
            except TimeoutException as e:
                self._take_auth_screenshot("facebook_timeout")
                self.logger.error(f"Timeout during Facebook login: {str(e)}")
                retry_count += 1
                if retry_count <= max_retries:
                    self.logger.warning(f"Retrying Facebook login ({retry_count}/{max_retries})...")
                    time.sleep(3)
                else:
                    return False, f"Timeout during login: {str(e)}"
                    
            except Exception as e:
                self._take_auth_screenshot("facebook_error")
                self.logger.error(f"Error during Facebook login: {str(e)}")
                return False, f"Error during login: {str(e)}"
        
        return False, "Login failed after maximum retries"
    
    def login_instagram(self, max_retries=2):
        """
        Log in to Instagram using credentials from environment variables.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, message)
        """
        platform = 'instagram'
        self.logger.info("Attempting to log in to Instagram...")
        
        # Check if credentials are available
        if not self.credentials[platform]['username'] or not self.credentials[platform]['password']:
            return False, "Instagram credentials not found in environment variables"
            
        # Get credentials
        username = self.credentials[platform]['username']
        password = self.credentials[platform]['password']
        
        retry_count = 0
        while retry_count <= max_retries:
            try:
                # Navigate to Instagram login page
                self.driver.get("https://www.instagram.com/accounts/login/")
                time.sleep(3)  # Wait for page to load
                
                # Check if we're already logged in
                if self._is_instagram_logged_in():
                    self.logger.info("Already logged in to Instagram")
                    return True, "Already logged in"
                
                # Handle cookie consent
                self.handle_cookie_consent('instagram')
                
                # Enter username
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username']"))
                )
                username_field.clear()
                username_field.send_keys(username)
                
                # Enter password
                password_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
                )
                password_field.clear()
                password_field.send_keys(password)
                
                # Click login button
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                )
                login_button.click()
                
                # Wait for home page to load
                time.sleep(5)
                
                # Handle "Save Login Info" prompt if it appears
                try:
                    not_now_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
                    )
                    not_now_button.click()
                    time.sleep(2)
                except TimeoutException:
                    # No "Save Login Info" prompt, continue
                    pass
                
                # Handle notifications prompt if it appears
                try:
                    not_now_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
                    )
                    not_now_button.click()
                    time.sleep(2)
                except TimeoutException:
                    # No notifications prompt, continue
                    pass
                
                # Verify login success
                if self._is_instagram_logged_in():
                    self.logger.info("Successfully logged in to Instagram")
                    return True, "Login successful"
                else:
                    # Take screenshot for debugging
                    self._take_auth_screenshot("instagram_failed")
                    
                    # Check for specific error messages
                    if "Verify Your Identity" in self.driver.page_source or "suspicious" in self.driver.page_source.lower():
                        self.logger.warning("Instagram login requires identity verification")
                        return False, "Identity verification required"
                    
                    retry_count += 1
                    if retry_count <= max_retries:
                        self.logger.warning(f"Instagram login failed, retrying ({retry_count}/{max_retries})...")
                        time.sleep(3)
                    else:
                        self.logger.error("Instagram login failed after maximum retries")
                        return False, "Login failed after maximum retries"
            
            except TimeoutException as e:
                self._take_auth_screenshot("instagram_timeout")
                self.logger.error(f"Timeout during Instagram login: {str(e)}")
                retry_count += 1
                if retry_count <= max_retries:
                    self.logger.warning(f"Retrying Instagram login ({retry_count}/{max_retries})...")
                    time.sleep(3)
                else:
                    return False, f"Timeout during login: {str(e)}"
                    
            except Exception as e:
                self._take_auth_screenshot("instagram_error")
                self.logger.error(f"Error during Instagram login: {str(e)}")
                return False, f"Error during login: {str(e)}"
        
        return False, "Login failed after maximum retries"
    
    def handle_cookie_consent(self, platform):
        """
        Handle cookie consent prompts with comprehensive selectors for different platforms.
        
        Args:
            platform: The platform to handle cookie consent for
            
        Returns:
            Boolean indicating if a cookie consent button was found and clicked
        """
        try:
            self.logger.info(f"Checking for cookie consent prompts on {platform}")
            
            # More comprehensive selectors for cookie consent buttons
            selectors = [
                # Generic selectors
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow all')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept cookies')]",
                "//button[contains(@id, 'accept') or contains(@class, 'accept')]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
                
                # Platform-specific selectors
                "//button[@data-cookiebanner='accept_button']",  # Facebook
                "//button[contains(@class, 'js-cookie-consent-agree')]",  # Instagram
                "//div[@role='button' and contains(., 'Accept')]",  # Twitter
                "//div[contains(@role, 'dialog')]//div[@role='button' and contains(., 'Accept')]",  # Twitter dialog
            ]
            
            # Add platform-specific selectors
            if platform.lower() == 'facebook':
                selectors.extend([
                    "//button[contains(@title, 'Accept')]",
                    "//button[contains(@title, 'Allow')]",
                    "//button[contains(text(), 'Only allow essential cookies')]"
                ])
            elif platform.lower() == 'instagram':
                selectors.extend([
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(@class, 'aOOlW')]"  # Instagram's cookie button class
                ])
            elif platform.lower() == 'twitter':
                selectors.extend([
                    "//span[contains(text(), 'Accept all cookies')]/ancestor::div[@role='button']",
                    "//span[text()='Accept']/ancestor::div[@role='button']"
                ])
            
            # Try each selector
            for selector in selectors:
                try:
                    cookie_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    self.logger.info(f"Found cookie consent button for {platform} with selector: {selector}")
                    cookie_button.click()
                    time.sleep(1)
                    return True
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException):
                    continue
                    
            # If we get here, no button was found
            self.logger.info(f"No cookie consent button found for {platform}")
            return False
            
        except Exception as e:
            self.logger.warning(f"Error handling cookie consent: {str(e)}")
            return False
    
    def _check_login_status(self, platform, extended_check=False):
        """
        Check if we're logged in to a platform with extended verification.
        
        Args:
            platform: The platform to check (twitter, facebook, instagram)
            extended_check: Whether to perform extended verification
            
        Returns:
            Boolean indicating login status
        """
        try:
            if platform.lower() == "twitter":
                # Basic check first
                basic_check = (
                    "Home" in self.driver.page_source and 
                    ("Explore" in self.driver.page_source or "Search" in self.driver.page_source) and
                    not "Log in" in self.driver.page_source
                )
                
                if not basic_check:
                    return False
                    
                if extended_check:
                    # Look for elements that definitively indicate logged-in state
                    try:
                        profile_elements = self.driver.find_elements(By.XPATH, 
                            "//a[contains(@href, '/home')] | //a[contains(@data-testid, 'AppTabBar_Profile_Link')]")
                        return len(profile_elements) > 0
                    except:
                        return False
                return True
                
            elif platform.lower() == "facebook":
                # Basic check first
                basic_check = (
                    "Search Facebook" in self.driver.page_source or
                    "What's on your mind" in self.driver.page_source or
                    "Create Post" in self.driver.page_source
                )
                
                if not basic_check:
                    return False
                    
                if extended_check:
                    # Look for elements that definitively indicate logged-in state
                    try:
                        profile_elements = self.driver.find_elements(By.XPATH, 
                            "//div[@aria-label='Your profile'] | //a[contains(@href, '/me') or contains(@href, '/profile.php')]")
                        return len(profile_elements) > 0
                    except:
                        return False
                return True
                
            elif platform.lower() == "instagram":
                # Basic check first
                basic_check = (
                    "Search" in self.driver.page_source and
                    "Profile" in self.driver.page_source and
                    not "Log In" in self.driver.page_source
                )
                
                if not basic_check:
                    return False
                    
                if extended_check:
                    # Look for elements that definitively indicate logged-in state
                    try:
                        # Look for navigation elements or profile icon that only appear when logged in
                        nav_elements = self.driver.find_elements(By.XPATH, 
                            "//a[contains(@href, '/direct/inbox/')] | //a[contains(@href, '/explore/')] | //div[@role='navigation']//a[contains(@href, '/')]")
                        
                        # If we find the avatar element, we're definitely logged in
                        avatar = self.driver.find_elements(By.XPATH, "//img[@data-testid='user-avatar']")
                        
                        return len(nav_elements) > 0 or len(avatar) > 0
                    except:
                        return False
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking login status for {platform}: {str(e)}")
            return False
    
    def _is_twitter_logged_in(self):
        """Check if we're logged in to Twitter."""
        return self._check_login_status("twitter")
    
    def _is_facebook_logged_in(self):
        """Check if we're logged in to Facebook."""
        return self._check_login_status("facebook")
    
    def _is_instagram_logged_in(self):
        """Check if we're logged in to Instagram."""
        return self._check_login_status("instagram")
    
    def _take_auth_screenshot(self, prefix):
        """Take a screenshot for debugging authentication issues."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            screenshot_path = os.path.join(self.screenshot_dir, filename)
            self.driver.save_screenshot(screenshot_path)
            self.logger.info(f"Authentication screenshot saved to {screenshot_path}")
        except Exception as e:
            self.logger.error(f"Failed to take authentication screenshot: {str(e)}")
    
    def is_authenticated(self, platform):
        """
        Check if we're authenticated with a specific platform.
        
        Args:
            platform: The platform to check ('twitter', 'facebook', or 'instagram')
            
        Returns:
            Boolean indicating authentication status
        """
        return self.auth_status.get(platform.lower(), False)
