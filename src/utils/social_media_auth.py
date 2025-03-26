import os
import time
import json
import random
import pickle
import string
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    ElementClickInterceptedException, StaleElementReferenceException,
    ElementNotInteractableException, JavascriptException
)

class SocialMediaAuth:
    """
    Enhanced authentication handler for social media platforms.
    Supports Twitter, Facebook, and Instagram with robust session management.
    """
    
    def __init__(self, driver, logger, screenshot_dir=None):
        """
        Initialize the enhanced authentication module.
        
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
        
        # Set up session storage directory
        self.session_dir = os.path.join("data", "sessions")
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
            
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
        
        # Track authentication status with timestamps
        self.auth_status = {
            'facebook': {
                'logged_in': False,
                'last_verified': None,
                'last_login_attempt': None,
                'session_id': None
            },
            'instagram': {
                'logged_in': False,
                'last_verified': None,
                'last_login_attempt': None,
                'session_id': None
            },
            'twitter': {
                'logged_in': False,
                'last_verified': None,
                'last_login_attempt': None,
                'session_id': None
            }
        }
        
        # Maximum age of session verification before requiring re-verification (in seconds)
        self.verification_max_age = 600  # 10 minutes
        
        # Maximum number of login attempts per platform
        self.max_login_attempts = 3
        
        # Track login attempts
        self.login_attempts = {
            'facebook': 0,
            'instagram': 0,
            'twitter': 0
        }
        
        # Session age limit (in hours) - IMPORTANT: must be defined before _load_session_pool
        self.session_max_age = 12
        
        # Initialize session pool for each platform
        self.session_pool = self._load_session_pool()
        
        # Human-like typing speed range (time between keystrokes in seconds)
        self.type_speed_range = (0.05, 0.15)
    
    def _load_session_pool(self):
        """Load saved sessions from disk."""
        session_pool = {
            'facebook': [],
            'instagram': [],
            'twitter': []
        }
        
        try:
            session_file = os.path.join(self.session_dir, "session_pool.pkl")
            if os.path.exists(session_file):
                with open(session_file, 'rb') as f:
                    loaded_pool = pickle.load(f)
                    
                    # Filter out expired sessions
                    now = datetime.now()
                    expiration = now - timedelta(hours=self.session_max_age)
                    
                    for platform in session_pool:
                        if platform in loaded_pool:
                            session_pool[platform] = [
                                session for session in loaded_pool[platform]
                                if 'timestamp' in session and 
                                datetime.fromisoformat(session['timestamp']) > expiration
                            ]
                            
                self.logger.info(f"Loaded session pool from disk with {sum(len(sessions) for sessions in session_pool.values())} valid sessions")
        except Exception as e:
            self.logger.error(f"Error loading session pool: {str(e)}")
        
        return session_pool
    
    def _save_session_pool(self):
        """Save current session pool to disk."""
        try:
            session_file = os.path.join(self.session_dir, "session_pool.pkl")
            with open(session_file, 'wb') as f:
                pickle.dump(self.session_pool, f)
            self.logger.info("Saved session pool to disk")
        except Exception as e:
            self.logger.error(f"Error saving session pool: {str(e)}")
    
    def _type_like_human(self, element, text):
        """Type text with random delays to simulate human typing."""
        for character in text:
            element.send_keys(character)
            time.sleep(random.uniform(*self.type_speed_range))
    
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
    
    def _save_current_session(self, platform):
        """
        Save current browser session for reuse.
        
        Args:
            platform: The platform to save session for
        """
        try:
            # Generate a unique session ID
            session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            
            # Get cookies and local storage
            cookies = self.driver.get_cookies()
            local_storage = self.driver.execute_script("return Object.assign({}, window.localStorage);")
            
            # Create session object
            session = {
                'id': session_id,
                'cookies': cookies,
                'local_storage': local_storage,
                'timestamp': datetime.now().isoformat()
            }
            
            # Add to session pool
            self.session_pool[platform].append(session)
            
            # Update current session ID
            self.auth_status[platform]['session_id'] = session_id
            
            # Save updated session pool
            self._save_session_pool()
            
            self.logger.info(f"Saved {platform} session with ID {session_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Error saving session for {platform}: {str(e)}")
            return None
    
    def _restore_session(self, platform, session=None):
        """
        Restore a saved browser session.
        
        Args:
            platform: The platform to restore session for
            session: Specific session to restore, or None to use the latest
            
        Returns:
            Boolean indicating success
        """
        try:
            # If no specific session provided, use the latest valid one
            if not session:
                if not self.session_pool[platform]:
                    return False
                
                # Sort by timestamp and get the most recent
                sessions = sorted(
                    self.session_pool[platform], 
                    key=lambda s: datetime.fromisoformat(s['timestamp']), 
                    reverse=True
                )
                
                if not sessions:
                    return False
                
                session = sessions[0]
            
            # Navigate to the platform homepage
            if platform == 'facebook':
                self.driver.get('https://www.facebook.com/')
            elif platform == 'instagram':
                self.driver.get('https://www.instagram.com/')
            elif platform == 'twitter':
                self.driver.get('https://twitter.com/')
            else:
                return False
            
            # Clear existing cookies
            self.driver.delete_all_cookies()
            
            # Restore cookies
            for cookie in session['cookies']:
                # Skip cookies that might cause issues
                if 'expiry' in cookie:
                    # Some platforms use timestamps in seconds, some in milliseconds
                    if cookie['expiry'] > 32503680000:  # Year 3000 in milliseconds
                        # Convert to seconds for compatibility
                        cookie['expiry'] = int(cookie['expiry'] / 1000)
                
                try:
                    self.driver.add_cookie(cookie)
                except Exception as cookie_err:
                    self.logger.debug(f"Error adding cookie: {str(cookie_err)}")
            
            # Restore local storage
            if session.get('local_storage'):
                for key, value in session['local_storage'].items():
                    self.driver.execute_script(f"window.localStorage.setItem('{key}', '{value}');")
            
            # Refresh the page to activate the session
            self.driver.refresh()
            time.sleep(3)
            
            # Verify the session worked
            is_logged_in = self._check_login_status(platform, extended_check=True)
            
            if is_logged_in:
                self.logger.info(f"Successfully restored {platform} session {session['id']}")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                self.auth_status[platform]['session_id'] = session['id']
                return True
            else:
                self.logger.warning(f"Failed to restore {platform} session {session['id']}")
                # Remove failed session from pool
                self.session_pool[platform] = [s for s in self.session_pool[platform] if s['id'] != session['id']]
                self._save_session_pool()
                return False
                
        except Exception as e:
            self.logger.error(f"Error restoring session for {platform}: {str(e)}")
            return False
    
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
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'i agree')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
                
                # Platform-specific selectors
                "//button[@data-cookiebanner='accept_button']",  # Facebook
                "//button[contains(@class, 'js-cookie-consent-agree')]",  # Instagram
                "//div[@role='button' and contains(., 'Accept')]",  # Twitter
                "//div[contains(@role, 'dialog')]//div[@role='button' and contains(., 'Accept')]",  # Twitter dialog
                "//div[contains(@role, 'dialog')]//div[@role='button' and contains(., 'I agree')]",  # Generic dialog
                "//div[contains(@role, 'dialog')]//div[@role='button' and contains(., 'Continue')]",  # Generic dialog
            ]
            
            # Add platform-specific selectors
            if platform.lower() == 'facebook':
                selectors.extend([
                    "//button[contains(@title, 'Accept')]",
                    "//button[contains(@title, 'Allow')]",
                    "//button[contains(text(), 'Only allow essential cookies')]",
                    "//button[contains(@aria-label, 'Allow')]",
                    "//button[contains(@aria-label, 'Accept')]",
                    "//div[@aria-label='Allow all cookies']",
                    "//div[@aria-label='Accept all cookies']"
                ])
            elif platform.lower() == 'instagram':
                selectors.extend([
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(@class, 'aOOlW')]",  # Instagram's cookie button class
                    "//button[contains(text(), 'Allow')]",
                    "//button[contains(text(), 'OK')]",
                    "//button[contains(text(), 'I Agree')]"
                ])
            elif platform.lower() == 'twitter':
                selectors.extend([
                    "//span[contains(text(), 'Accept all cookies')]/ancestor::div[@role='button']",
                    "//span[text()='Accept']/ancestor::div[@role='button']",
                    "//span[contains(text(), 'I agree')]/ancestor::div[@role='button']",
                    "//span[contains(text(), 'Allow')]/ancestor::div[@role='button']",
                    "//div[@data-testid='BottomBar']//span[contains(text(), 'Accept')]/ancestor::div[@role='button']"
                ])
            
            # Check for cookie banners/dialogs first
            cookie_dialogs = [
                "//div[contains(@class, 'cookie')]",
                "//div[contains(@id, 'cookie')]",
                "//div[contains(@class, 'gdpr')]",
                "//div[contains(@id, 'gdpr')]",
                "//div[contains(@class, 'consent')]",
                "//div[contains(@id, 'consent')]",
                "//div[@role='dialog']"
            ]
            
            dialog_found = False
            dialog_selector = None
            for ds in cookie_dialogs:
                try:
                    dialog = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.XPATH, ds))
                    )
                    dialog_found = True
                    dialog_selector = ds
                    self.logger.info(f"Found cookie dialog for {platform} with selector: {ds}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # If no dialog found, we might not need to handle cookies
            if not dialog_found:
                self.logger.info(f"No cookie dialog found for {platform}")
                return False
            
            # Try each selector
            for selector in selectors:
                try:
                    cookie_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    self.logger.info(f"Found cookie consent button for {platform} with selector: {selector}")
                    
                    # Try to click with JavaScript if regular click fails
                    try:
                        cookie_button.click()
                    except (ElementClickInterceptedException, StaleElementReferenceException):
                        self.driver.execute_script("arguments[0].click();", cookie_button)
                        
                    time.sleep(1)
                    
                    # Check if the dialog is still visible
                    if dialog_found and dialog_selector:
                        try:
                            WebDriverWait(self.driver, 2).until_not(
                                EC.visibility_of_element_located((By.XPATH, dialog_selector))
                            )
                            self.logger.info(f"Cookie dialog closed successfully for {platform}")
                        except TimeoutException:
                            self.logger.info(f"Cookie dialog may still be visible for {platform}, trying next selector")
                            continue
                        
                    return True
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException):
                    continue
                    
            # If we get here, no button was found or clicked successfully
            self.logger.info(f"No cookie consent button found or clicked successfully for {platform}")
            
            # Last resort: try to click any button in the cookie dialog
            if dialog_found and dialog_selector:
                try:
                    buttons = self.driver.find_elements(By.XPATH, f"{dialog_selector}//button")
                    if buttons:
                        self.logger.info(f"Trying last resort: clicking first button in cookie dialog for {platform}")
                        try:
                            buttons[0].click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", buttons[0])
                        time.sleep(1)
                        return True
                except Exception:
                    pass
                    
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
            # Make sure we're on the platform's page before checking
            current_url = self.driver.current_url.lower()
            if platform.lower() == "twitter" and "twitter.com" not in current_url:
                self.driver.get("https://twitter.com/home")
                time.sleep(3)
            elif platform.lower() == "facebook" and "facebook.com" not in current_url:
                self.driver.get("https://www.facebook.com/")
                time.sleep(3)
            elif platform.lower() == "instagram" and "instagram.com" not in current_url:
                self.driver.get("https://www.instagram.com/")
                time.sleep(3)
                
            # Handle any cookie consent dialogs that might appear
            self.handle_cookie_consent(platform)
                
            if platform.lower() == "twitter":
                return self._is_twitter_logged_in(extended_check)
            elif platform.lower() == "facebook":
                return self._is_facebook_logged_in(extended_check)
            elif platform.lower() == "instagram":
                return self._is_instagram_logged_in(extended_check)
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking login status for {platform}: {str(e)}")
            return False
    
    def _is_twitter_logged_in(self, extended_check=False):
        """Check if we're logged in to Twitter."""
        try:
            # Check for negative indicators first - these always indicate we're NOT logged in
            negative_indicators = [
                "//a[contains(text(), 'Log in')]",
                "//a[contains(text(), 'Sign up')]", 
                "//div[@data-testid='loginButton']",
                "//span[contains(text(), 'Log in')]/ancestor::a",
                "//span[contains(text(), 'Sign up')]/ancestor::a",
                "//form[contains(@action, 'session')]"
            ]
            
            for indicator in negative_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        self.logger.info(f"Twitter login negative indicator found: {indicator}")
                        return False  # Definitely not logged in
                except Exception:
                    pass
            
            # Basic check now
            basic_check = (
                "Home" in self.driver.page_source and 
                ("Explore" in self.driver.page_source or "Search" in self.driver.page_source) and
                "Log in" not in self.driver.page_source
            )
            
            if not basic_check:
                self.logger.info("Twitter basic login check failed")
                return False
                
            # Always do extended check - it's more reliable
            # Look for elements that definitively indicate logged-in state
            try:
                profile_elements = self.driver.find_elements(By.XPATH, 
                    "//a[contains(@href, '/home')] | //a[contains(@data-testid, 'AppTabBar_Profile_Link')] | " +
                    "//div[@data-testid='SideNav_AccountSwitcher_Button'] | //a[@aria-label='Profile']")
                
                if len(profile_elements) == 0:
                    self.logger.info("Twitter profile elements not found")
                    return False
                
                # Take a screenshot to verify login status
                self._take_auth_screenshot("twitter_login_verification")
                
                self.logger.info("Twitter login verified via profile elements")
                return True
            except Exception as e:
                self.logger.error(f"Error in Twitter extended login check: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error checking Twitter login status: {str(e)}")
            return False
    
    def _is_twitter_logged_in_comprehensive(self):
        """Perform a comprehensive check to verify Twitter login status."""
        try:
            # Check for common elements that indicate logged-in state
            indicators = [
                # Home timeline
                "//div[@data-testid='primaryColumn']",
                # Sidebar navigation
                "//nav[@aria-label='Primary']",
                # Profile icon
                "//div[@data-testid='SideNav_AccountSwitcher_Button']",
                # Tweet button
                "//a[@data-testid='SideNav_NewTweet_Button']"
            ]
            
            # Check for negative indicators
            negative_indicators = [
                # Login button
                "//a[contains(text(), 'Log in')]",
                # Sign up button
                "//a[contains(text(), 'Sign up')]",
                # Login form
                "//form[contains(@action, 'session')]"
            ]
            
            # Count positive and negative indicators
            positive_count = 0
            for indicator in indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        positive_count += 1
                except Exception:
                    pass
            
            # Check for any negative indicators
            for indicator in negative_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        return False  # Found negative indicator
                except Exception:
                    pass
            
            # Must have at least 2 positive indicators and no negative indicators
            return positive_count >= 2
        except Exception as e:
            self.logger.error(f"Error in comprehensive Twitter login check: {str(e)}")
            return False
    
    def _is_facebook_logged_in(self, extended_check=False):
        """Check if we're logged in to Facebook."""
        try:
            # Check for negative indicators first - these always indicate we're NOT logged in
            negative_indicators = [
                "//form[contains(@action, 'login')]",
                "//button[@name='login']",
                "//a[contains(text(), 'Create New Account')]",
                "//a[contains(text(), 'Sign Up')]",
                "//div[contains(text(), 'Log Into Facebook')]"
            ]
            
            for indicator in negative_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        self.logger.info(f"Facebook login negative indicator found: {indicator}")
                        return False  # Definitely not logged in
                except Exception:
                    pass
            
            # Basic check now
            basic_check = (
                "Search Facebook" in self.driver.page_source or
                "What's on your mind" in self.driver.page_source or
                "Create Post" in self.driver.page_source
            )
            
            if not basic_check:
                self.logger.info("Facebook basic login check failed")
                return False
                
            # Always do extended check - it's more reliable
            # Look for elements that definitively indicate logged-in state
            try:
                profile_elements = self.driver.find_elements(By.XPATH, 
                    "//div[@aria-label='Your profile'] | //a[contains(@href, '/me') or contains(@href, '/profile.php')] | " +
                    "//div[@aria-label='Your profile'] | //div[contains(@aria-label, 'Account')]")
                    
                if len(profile_elements) == 0:
                    self.logger.info("Facebook profile elements not found")
                    return False
                
                # Take a screenshot to verify login status
                self._take_auth_screenshot("facebook_login_verification")
                
                self.logger.info("Facebook login verified via profile elements")
                return True
            except Exception as e:
                self.logger.error(f"Error in Facebook extended login check: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error checking Facebook login status: {str(e)}")
            return False
    
    def _is_facebook_logged_in_comprehensive(self):
        """Perform a comprehensive check to verify Facebook login status."""
        try:
            # Check for common elements that indicate logged-in state
            indicators = [
                # Navigation bar
                "//div[@role='navigation']",
                # Profile link
                "//a[contains(@href, '/me') or contains(@href, '/profile.php')]",
                # Create post
                "//div[contains(text(), 'What') and contains(text(), 'on your mind')]",
                # Account menu
                "//div[@aria-label='Account' or contains(@aria-label, 'Your profile')]"
            ]
            
            # Check for negative indicators
            negative_indicators = [
                # Login form
                "//form[contains(@action, 'login')]",
                # Login button
                "//button[@name='login']",
                # Create account button
                "//a[contains(text(), 'Create New Account') or contains(text(), 'Sign Up')]"
            ]
            
            # Count positive and negative indicators
            positive_count = 0
            for indicator in indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        positive_count += 1
                except Exception:
                    pass
            
            # Check for any negative indicators
            for indicator in negative_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        return False  # Found negative indicator
                except Exception:
                    pass
            
            # Must have at least 2 positive indicators and no negative indicators
            return positive_count >= 2
        except Exception as e:
            self.logger.error(f"Error in comprehensive Facebook login check: {str(e)}")
            return False
    
    def _is_instagram_logged_in(self, extended_check=False):
        """Check if we're logged in to Instagram."""
        try:
            # Check for negative indicators first - these always indicate we're NOT logged in
            negative_indicators = [
                "//form[contains(@id, 'loginForm')]",
                "//button[contains(text(), 'Log In')]",
                "//a[contains(text(), 'Sign up')]",
                "//input[@name='username']",
                "//input[@name='password']"
            ]
            
            for indicator in negative_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        self.logger.info(f"Instagram login negative indicator found: {indicator}")
                        return False  # Definitely not logged in
                except Exception:
                    pass
            
            # Basic check now
            basic_check = (
                "Search" in self.driver.page_source and
                "Profile" in self.driver.page_source and
                "Log In" not in self.driver.page_source
            )
            
            if not basic_check:
                self.logger.info("Instagram basic login check failed")
                return False
                
            # Always do extended check - it's more reliable
            # Look for elements that definitively indicate logged-in state
            try:
                # Look for navigation elements or profile icon that only appear when logged in
                nav_elements = self.driver.find_elements(By.XPATH, 
                    "//a[contains(@href, '/direct/inbox/')] | //a[contains(@href, '/explore/')] | " +
                    "//div[@role='navigation']//a[contains(@href, '/')] | //a[contains(@href, '/accounts/activity/')]")
                
                # If we find the avatar element, we're definitely logged in
                avatar = self.driver.find_elements(By.XPATH, 
                    "//img[@data-testid='user-avatar'] | //span[@role='link' and contains(@class, 'coreSpriteDesktopNavProfile')]")
                
                if len(nav_elements) == 0 and len(avatar) == 0:
                    self.logger.info("Instagram profile elements not found")
                    return False
                
                # Take a screenshot to verify login status
                self._take_auth_screenshot("instagram_login_verification")
                
                self.logger.info("Instagram login verified via profile elements")
                return True
            except Exception as e:
                self.logger.error(f"Error in Instagram extended login check: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error checking Instagram login status: {str(e)}")
            return False
    
    def _is_instagram_logged_in_comprehensive(self):
        """Perform a comprehensive check to verify Instagram login status."""
        try:
            # Check for common elements that indicate logged-in state
            indicators = [
                # Navigation bar
                "//div[@role='navigation']",
                # Direct messages icon
                "//a[contains(@href, '/direct/inbox/')]",
                # Profile icon
                "//a[contains(@href, '/accounts/activity/')]",
                # Home feed elements
                "//div[@role='feed']",
                # Search box
                "//input[@placeholder='Search']"
            ]
            
            # Check for negative indicators
            negative_indicators = [
                # Login form
                "//form[contains(@id, 'loginForm')]",
                # Login button
                "//button[contains(text(), 'Log In')]",
                # Sign up link
                "//a[contains(text(), 'Sign up')]"
            ]
            
            # Count positive and negative indicators
            positive_count = 0
            for indicator in indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        positive_count += 1
                except Exception:
                    pass
            
            # Check for any negative indicators
            for indicator in negative_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    if elements and len(elements) > 0 and elements[0].is_displayed():
                        return False  # Found negative indicator
                except Exception:
                    pass
            
            # Must have at least 2 positive indicators and no negative indicators
            return positive_count >= 2
        except Exception as e:
            self.logger.error(f"Error in comprehensive Instagram login check: {str(e)}")
            return False

    def login_instagram(self, max_retries=2):
        """
        Log in to Instagram using credentials from environment variables with enhanced reliability.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, message)
        """
        platform = 'instagram'
        self.logger.info("Attempting to log in to Instagram...")
        
        if not self.credentials[platform]['username'] or not self.credentials[platform]['password']:
            self.logger.error("Instagram credentials are missing.")
            return False, "Instagram credentials missing"
        
        # Track login attempt
        self.login_attempts[platform] += 1
        self.auth_status[platform]['last_login_attempt'] = datetime.now()
        
        # If we've exceeded max retries, abort
        if self.login_attempts[platform] > max_retries:
            self.logger.warning(f"Exceeded maximum Instagram login attempts ({max_retries})")
            return False, "Exceeded maximum login attempts"
        
        try:
            # Navigate to Instagram
            self.driver.get("https://www.instagram.com/")
            time.sleep(3)
            
            # Handle cookie consent prompt if needed
            self.handle_cookie_consent(platform)
            
            # Check if we're already logged in
            if self._is_instagram_logged_in():
                self.logger.info("Already logged in to Instagram")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                
                # Save session if we don't have one
                if not self.auth_status[platform]['session_id']:
                    self._save_current_session(platform)
                    
                return True, "Already logged in"
            
            # Wait for login page to load and find username field
            try:
                username_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username']"))
                )
            except TimeoutException:
                self.logger.error("Instagram login page did not load correctly (username field not found)")
                return False, "Login page failed to load"
            
            # Enter credentials with human-like typing
            username_input.clear()
            self._type_like_human(username_input, self.credentials[platform]['username'])
            
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[name='password']")
            password_input.clear()
            self._type_like_human(password_input, self.credentials[platform]['password'])
            
            # Take a screenshot for debugging before submitting
            self._take_auth_screenshot(f"instagram_login_pre_submit")
            
            # Submit login form
            try:
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
            except NoSuchElementException:
                # Try alternate login button
                try:
                    login_button = self.driver.find_element(By.XPATH, "//div[text()='Log In']/ancestor::button")
                    login_button.click()
                except NoSuchElementException:
                    self.logger.error("Instagram login button not found")
                    return False, "Login button not found"
            
            # Wait for the page to load
            time.sleep(5)
            
            # Check for "Save login info" dialog and click "Not Now" if exists
            try:
                save_info_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[text()='Not Now']"))
                )
                save_info_button.click()
                time.sleep(2)
            except TimeoutException:
                self.logger.info("No 'Save login info' prompt detected on Instagram")
            
            # Check for "Turn on Notifications" dialog and click "Not Now" if exists
            try:
                notif_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[text()='Not Now']"))
                )
                notif_button.click()
                time.sleep(2)
            except TimeoutException:
                self.logger.info("No notification prompt detected on Instagram")
            
            # Verify login success
            time.sleep(3)  # Give page time to load fully
            
            # Take a screenshot for debugging after login attempt
            self._take_auth_screenshot(f"instagram_login_post_submit")
            
            # Perform comprehensive validation of login status
            is_logged_in = self._is_instagram_logged_in(extended_check=True)
            
            # Handle the result
            if is_logged_in:
                self.logger.info("Successfully logged in to Instagram")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                # Save session for future use
                self._save_current_session(platform)
                self.login_attempts[platform] = 0  # Reset counter after success
                return True, "Login successful"
            else:
                self.logger.warning("Instagram login attempt failed")
                
                # Check if there's an error message
                try:
                    error_message = self.driver.find_element(By.ID, "slfErrorAlert").text
                    self.logger.error(f"Instagram login error: {error_message}")
                    return False, f"Login failed: {error_message}"
                except NoSuchElementException:
                    pass
                
                return False, "Login verification failed"
                
        except Exception as e:
            self.logger.error(f"Error during Instagram login: {str(e)}")
            return False, f"Error: {str(e)}"

    def login_facebook(self, max_retries=2):
        """
        Log in to Facebook using credentials from environment variables with enhanced reliability.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, message)
        """
        platform = 'facebook'
        self.logger.info("Attempting to log in to Facebook...")
        
        if not self.credentials[platform]['email'] or not self.credentials[platform]['password']:
            self.logger.error("Facebook credentials are missing.")
            return False, "Facebook credentials missing"
        
        # Track login attempt
        self.login_attempts[platform] += 1
        self.auth_status[platform]['last_login_attempt'] = datetime.now()
        
        # If we've exceeded max retries, abort
        if self.login_attempts[platform] > max_retries:
            self.logger.warning(f"Exceeded maximum Facebook login attempts ({max_retries})")
            return False, "Exceeded maximum login attempts"
        
        try:
            # Navigate to Facebook
            self.driver.get("https://www.facebook.com/")
            time.sleep(3)
            
            # Handle cookie consent prompt if needed
            self.handle_cookie_consent(platform)
            
            # Check if we're already logged in
            if self._is_facebook_logged_in():
                self.logger.info("Already logged in to Facebook")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                
                # Save session if we don't have one
                if not self.auth_status[platform]['session_id']:
                    self._save_current_session(platform)
                    
                return True, "Already logged in"
            
            # Wait for login page to load and find email field
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "email"))
                )
            except TimeoutException:
                self.logger.error("Facebook login page did not load correctly (email field not found)")
                return False, "Login page failed to load"
            
            # Enter credentials with human-like typing
            email_input.clear()
            self._type_like_human(email_input, self.credentials[platform]['email'])
            
            password_input = self.driver.find_element(By.ID, "pass")
            password_input.clear()
            self._type_like_human(password_input, self.credentials[platform]['password'])
            
            # Take a screenshot for debugging before submitting
            self._take_auth_screenshot(f"facebook_login_pre_submit")
            
            # Submit login form
            try:
                login_button = self.driver.find_element(By.NAME, "login")
                login_button.click()
            except NoSuchElementException:
                self.logger.error("Facebook login button not found")
                return False, "Login button not found"
            
            # Wait for the page to load
            time.sleep(5)
            
            # Take a screenshot for debugging after login attempt
            self._take_auth_screenshot(f"facebook_login_post_submit")
            
            # Verify login success
            is_logged_in = self._is_facebook_logged_in(extended_check=True)
            
            # Handle the result
            if is_logged_in:
                self.logger.info("Successfully logged in to Facebook")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                # Save session for future use
                self._save_current_session(platform)
                self.login_attempts[platform] = 0  # Reset counter after success
                return True, "Login successful"
            else:
                self.logger.warning("Facebook login attempt failed")
                return False, "Login verification failed"
                
        except Exception as e:
            self.logger.error(f"Error during Facebook login: {str(e)}")
            return False, f"Error: {str(e)}"

    def login_twitter(self, max_retries=2):
        """
        Log in to Twitter using credentials from environment variables with enhanced reliability.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (success, message)
        """
        platform = 'twitter'
        self.logger.info("Attempting to log in to Twitter...")
        
        if not (self.credentials[platform]['email'] or self.credentials[platform]['username']) or not self.credentials[platform]['password']:
            self.logger.error("Twitter credentials are missing.")
            return False, "Twitter credentials missing"
        
        # Track login attempt
        self.login_attempts[platform] += 1
        self.auth_status[platform]['last_login_attempt'] = datetime.now()
        
        # If we've exceeded max retries, abort
        if self.login_attempts[platform] > max_retries:
            self.logger.warning(f"Exceeded maximum Twitter login attempts ({max_retries})")
            return False, "Exceeded maximum login attempts"
        
        try:
            # Navigate to Twitter
            self.driver.get("https://twitter.com/i/flow/login")
            time.sleep(3)
            
            # Handle cookie consent prompt if needed
            self.handle_cookie_consent(platform)
            
            # Check if we're already logged in (in case we got redirected to home)
            if self._is_twitter_logged_in():
                self.logger.info("Already logged in to Twitter")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                
                # Save session if we don't have one
                if not self.auth_status[platform]['session_id']:
                    self._save_current_session(platform)
                    
                return True, "Already logged in"
            
            # Wait for login page to load and find username/email field
            try:
                username_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[autocomplete='username']"))
                )
            except TimeoutException:
                self.logger.error("Twitter login page did not load correctly (username field not found)")
                return False, "Login page failed to load"
            
            # Enter username/email with human-like typing
            username_input.clear()
            
            # Use email if available, otherwise use username
            user_identifier = self.credentials[platform]['email'] if self.credentials[platform]['email'] else self.credentials[platform]['username']
            self._type_like_human(username_input, user_identifier)
            
            # Take a screenshot for debugging
            self._take_auth_screenshot(f"twitter_login_username")
            
            # Click the Next button 
            try:
                next_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][.//span[contains(text(), 'Next')]]"))
                )
                next_button.click()
                time.sleep(2)
            except (TimeoutException, NoSuchElementException):
                self.logger.error("Twitter 'Next' button not found")
                return False, "Next button not found"
            
            # Check if we need to enter our username for verification (if we logged in with email)
            try:
                username_verification = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@data-testid='ocfEnterTextTextInput']"))
                )
                if username_verification and self.credentials[platform]['username']:
                    self._type_like_human(username_verification, self.credentials[platform]['username'])
                    # Click the Next button again
                    verify_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][.//span[contains(text(), 'Next')]]"))
                    )
                    verify_button.click()
                    time.sleep(2)
            except TimeoutException:
                self.logger.info("No username verification required")
            
            # Now enter password
            try:
                password_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
                )
                password_input.clear()
                self._type_like_human(password_input, self.credentials[platform]['password'])
            except TimeoutException:
                self.logger.error("Twitter password field not found")
                return False, "Password field not found"
            
            # Take a screenshot for debugging before submitting
            self._take_auth_screenshot(f"twitter_login_pre_submit")
            
            # Click the Log in button
            try:
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][.//span[contains(text(), 'Log in')]]"))
                )
                login_button.click()
            except (TimeoutException, NoSuchElementException):
                self.logger.error("Twitter login button not found")
                return False, "Login button not found"
            
            # Wait for the page to load
            time.sleep(5)
            
            # Take a screenshot for debugging after login attempt
            self._take_auth_screenshot(f"twitter_login_post_submit")
            
            # Verify login success
            is_logged_in = self._is_twitter_logged_in(extended_check=True)
            
            # Handle the result
            if is_logged_in:
                self.logger.info("Successfully logged in to Twitter")
                self.auth_status[platform]['logged_in'] = True
                self.auth_status[platform]['last_verified'] = datetime.now()
                # Save session for future use
                self._save_current_session(platform)
                self.login_attempts[platform] = 0  # Reset counter after success
                return True, "Login successful"
            else:
                self.logger.warning("Twitter login attempt failed")
                
                # Check for error messages
                try:
                    error_message = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='error-message']").text
                    self.logger.error(f"Twitter login error: {error_message}")
                    return False, f"Login failed: {error_message}"
                except NoSuchElementException:
                    pass
                
                return False, "Login verification failed"
                
        except Exception as e:
            self.logger.error(f"Error during Twitter login: {str(e)}")
            return False, f"Error: {str(e)}"

    def authenticate_all(self, platforms=None, force_login=False, use_cached_sessions=True):
        """
        Authenticate to all specified social media platforms.
        
        Args:
            platforms: List of platform names to authenticate to, or None for all
            force_login: Whether to force login even if already logged in
            use_cached_sessions: Whether to attempt to restore cached sessions
            
        Returns:
            Dict with results for each platform {platform: {'success': bool, 'message': str}}
        """
        if platforms is None:
            platforms = ['instagram', 'facebook', 'twitter']
        
        results = {}
        
        for platform in platforms:
            if platform not in self.auth_status:
                self.logger.warning(f"Unknown platform: {platform}")
                results[platform] = {'success': False, 'message': "Unknown platform"}
                continue
            
            # Check if we're already authenticated and within verification time window
            is_auth_valid = (
                self.auth_status[platform]['logged_in'] and 
                self.auth_status[platform]['last_verified'] and
                (datetime.now() - self.auth_status[platform]['last_verified']).total_seconds() < self.verification_max_age
            )
            
            if is_auth_valid and not force_login:
                self.logger.info(f"Already authenticated to {platform}, skipping login")
                results[platform] = {'success': True, 'message': "Already authenticated"}
                continue
                
            # Try restoring session first
            session_restored = False
            if use_cached_sessions and not force_login and self.session_pool[platform]:
                self.logger.info(f"Attempting to restore {platform} session...")
                session_restored = self._restore_session(platform)
                
                if session_restored:
                    self.logger.info(f"Successfully restored {platform} session")
                    results[platform] = {'success': True, 'message': "Session restored"}
                    continue
                else:
                    self.logger.info(f"Failed to restore {platform} session, trying to log in")
            
            # Direct login if no session or restore failed
            if platform == 'facebook':
                success, message = self.login_facebook()
            elif platform == 'twitter':
                success, message = self.login_twitter()
            elif platform == 'instagram':
                success, message = self.login_instagram()
            else:
                success, message = False, "Platform not supported"
                
            results[platform] = {'success': success, 'message': message}
            
            # If this login attempt failed, add a delay before trying next platform
            if not success:
                time.sleep(2)
                
        self.logger.info(f"Authentication results: {results}")
        return results
