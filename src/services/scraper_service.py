import time
import random
import urllib.parse
import re
import json
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from typing import Dict, Optional, List, Tuple, Any

class ScraperService:
    def __init__(self, driver, logger, success_logger, ai_verifier=None):
        self.driver = driver
        self.logger = logger
        self.success_logger = success_logger
        self.ai_verifier = ai_verifier
        self.search_engines = ['bing', 'duckduckgo']  # Start with Bing as it's more reliable
        self.current_engine = 0
        self.retry_count = 0
        self.max_retries = 3  # Keep for reliability

    def rotate_search_engine(self):
        """Rotate between search engines if one fails."""
        self.current_engine = (self.current_engine + 1) % len(self.search_engines)
        self.logger.info(f"Switching to {self.search_engines[self.current_engine]}")

    def get_search_url(self, query: str) -> str:
        """Construct a search URL with U.S. focus and flexible formatting."""
        encoded_query = urllib.parse.quote_plus(query)
        if self.search_engines[self.current_engine] == 'duckduckgo':
            # DuckDuckGo: U.S. region, no exact quotes unless necessary
            return f"https://duckduckgo.com/?q={encoded_query}&kl=us-en"
        else:
            # Bing: U.S. region, allow partial matches without excessive quotes
            return f"https://www.bing.com/search?q={encoded_query}&cc=us&setlang=en-US"

    def random_delay(self):
        """Introduce a balanced delay to avoid blocks while maintaining speed."""
        delay = random.uniform(1, 3)  # Keep 1-3s for reliability
        time.sleep(delay)

    def search_platform(self, query: str, platform: str, wait_time: int = 10) -> str:
        """Perform a reliable search with better timeout handling."""
        self.retry_count = 0
        while self.retry_count < self.max_retries:
            try:
                # Clear cookies and cache
                self.driver.delete_all_cookies()
                # Enhance anti-detection
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.driver.execute_script("""
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                """)
                # Simulate human behavior
                self.simulate_human_behavior()
                # Build and perform the search
                search_url = self.get_search_url(f"site:{platform} {query}" if platform else query)
                self.logger.info(f"Searching: {search_url}")
                self.driver.get(search_url)
                
                # Use fewer, more reliable selectors with shorter initial timeout
                primary_selectors = [
                    "div[data-testid='result']",  # DuckDuckGo
                    ".b_algo"                      # Bing
                ]
                
                # Try primary selectors with shorter timeout first
                for selector in primary_selectors:
                    try:
                        # Start with shorter timeout (5s)
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        # Ensure JavaScript has fully loaded
                        time.sleep(1)  # Shorter buffer for dynamic content
                        return self.driver.page_source
                    except TimeoutException:
                        # Just continue to next selector, don't log warning yet
                        continue
                
                # If primary selectors failed, try fallback selectors with original timeout
                fallback_selectors = [
                    "#links",                      # DuckDuckGo alternative
                    ".results",                    # Generic
                    "body"                         # Ultimate fallback - just get whatever loaded
                ]
                
                for selector in fallback_selectors:
                    try:
                        WebDriverWait(self.driver, wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        # Ensure JavaScript has fully loaded
                        time.sleep(1)  # Shorter buffer for dynamic content
                        return self.driver.page_source
                    except TimeoutException:
                        self.logger.warning(f"Timeout waiting for {selector} on {search_url}")
                        continue
                
                # If we got here, try to return whatever page source we have
                if self.driver.page_source and len(self.driver.page_source) > 1000:
                    self.logger.warning(f"Using partial page source for {search_url}")
                    return self.driver.page_source
                    
                # Otherwise rotate engine and retry
                self.rotate_search_engine()
            except WebDriverException as e:
                self.logger.warning(f"WebDriver error: {str(e)}")
                self.handle_error()
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")
                self.handle_error()
            self.retry_count += 1
        self.logger.error(f"All retries failed for query: {query}")
        return ""

    def handle_error(self):
        """Handle errors with balanced backoff for reliability."""
        wait_time = min(120, (2 ** self.retry_count) + random.uniform(1, 3))
        self.logger.info(f"Waiting {wait_time:.2f} seconds before retry")
        time.sleep(wait_time)
        self.rotate_search_engine()

    def simulate_human_behavior(self):
        """Simulate human-like interactions to avoid anti-scraping blocks."""
        try:
            scroll_amount = random.randint(200, 400)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(random.uniform(0.5, 1.5))
            self.driver.execute_script("""
                var event = new MouseEvent('mousemove', {
                    'clientX': arguments[0],
                    'clientY': arguments[1]
                });
                document.dispatchEvent(event);
            """, random.randint(100, 800), random.randint(100, 600))
        except Exception as e:
            self.logger.debug(f"Error in human simulation: {str(e)}")

    def get_profile_info(self, first_name: str, last_name: str, context: Dict[str, Any] = None) -> Dict[str, Optional[str]]:
        """Retrieve profile info using AI-driven search and verification."""
        full_name = f"{first_name} {last_name}"
        self.logger.info(f"Searching for {full_name}")
        
        # Initialize result structure
        result = {
            "email": None,
            "phone": None,
            "twitter": None,
            "facebook": None,
            "instagram": None
        }
        
        # Prepare athlete context
        athlete_info = {
            "First_Name": first_name,
            "Last_Name": last_name
        }
        
        # Add additional context if provided
        if context:
            athlete_info.update(context)
        
        # Define platform mapping
        platforms = {
            "twitter.com": "twitter",
            "facebook.com": "facebook",
            "instagram.com": "instagram"
        }
        
        # Use AI-driven search if available
        if self.ai_verifier:
            self.logger.info(f"Using AI-driven search for {full_name}")
            return self._ai_driven_search(athlete_info, platforms)
        else:
            # Fall back to traditional search
            self.logger.info(f"Using traditional search for {full_name} (AI verifier not available)")
            return self._traditional_search(first_name, last_name, platforms)
    
    def _ai_driven_search(self, athlete_info: Dict[str, Any], platforms: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Perform AI-driven search for athlete profiles."""
        full_name = f"{athlete_info['First_Name']} {athlete_info['Last_Name']}"
        result = {
            "email": None,
            "phone": None,
            "twitter": None,
            "facebook": None,
            "instagram": None
        }
        
        # Generate advanced search queries with AI
        queries, reasoning = self.ai_verifier.generate_advanced_search_queries(athlete_info)
        self.logger.info(f"AI generated {len(queries)} search queries for {full_name}")
        self.logger.debug(f"AI reasoning for queries: {reasoning[:200]}...")
        
        # Track candidate profiles across all searches
        all_candidates = []
        
        # Execute each search query
        for query in queries:
            self.logger.info(f"Executing AI-generated query: {query}")
            
            # Perform general search
            html = self.search_platform(query, "")
            if html:
                # Let AI analyze the search results
                candidates = self.ai_verifier.analyze_search_results(html, athlete_info)
                all_candidates.extend(candidates)
                
                # Extract contact info directly
                emails = self.extract_emails(html)
                phones = self.extract_phones(html)
                
                # Add emails and phones as candidates for AI verification
                for email in emails:
                    all_candidates.append({
                        "url": email,
                        "platform": "email",
                        "confidence": 0.5,  # Initial confidence
                        "reasoning": "Email found in search results"
                    })
                
                for phone in phones:
                    all_candidates.append({
                        "url": phone,
                        "platform": "phone",
                        "confidence": 0.5,  # Initial confidence
                        "reasoning": "Phone found in search results"
                    })
            
            # Also perform platform-specific searches
            for domain, key in platforms.items():
                platform_query = f"{query} site:{domain}"
                html = self.search_platform(platform_query, domain)
                if html:
                    # Let AI analyze the platform-specific results
                    platform_candidates = self.ai_verifier.analyze_search_results(html, athlete_info)
                    
                    # Add platform information
                    for candidate in platform_candidates:
                        candidate["platform"] = key
                    
                    all_candidates.extend(platform_candidates)
                    
                    # Also extract links directly as backup
                    links = self.extract_social_links(html, domain)
                    for link in links:
                        # Check if this link is already in candidates
                        if not any(c.get("url") == link for c in all_candidates):
                            all_candidates.append({
                                "url": link,
                                "platform": key,
                                "confidence": 0.4,  # Lower initial confidence
                                "reasoning": "Link extracted from platform-specific search"
                            })
                
                self.random_delay()
        
        # Group candidates by platform
        platform_candidates = {}
        for candidate in all_candidates:
            platform = candidate.get("platform")
            if platform and platform in result:
                if platform not in platform_candidates:
                    platform_candidates[platform] = []
                platform_candidates[platform].append(candidate)
        
        # Select the best candidate for each platform
        for platform, candidates in platform_candidates.items():
            # Sort by confidence
            sorted_candidates = sorted(candidates, key=lambda x: x.get("confidence", 0), reverse=True)
            
            if sorted_candidates:
                best_candidate = sorted_candidates[0]
                confidence = best_candidate.get("confidence", 0)
                url = best_candidate.get("url")
                
                # For high-confidence candidates, use directly
                if confidence > 0.8:
                    result[platform] = url
                    self.logger.info(f"High confidence match for {platform}: {url} ({confidence:.2f})")
                # For medium confidence, try to verify with profile content if possible
                elif confidence > 0.5 and platform in platforms.values():
                    try:
                        # Try to fetch and analyze the profile content
                        profile_content = self.fetch_profile_content(url)
                        is_match, verified_confidence, reasoning = self.ai_verifier.analyze_profile_content(
                            url, profile_content, athlete_info
                        )
                        
                        if is_match and verified_confidence > 0.6:
                            result[platform] = url
                            self.logger.info(f"Verified match for {platform}: {url} ({verified_confidence:.2f})")
                        else:
                            self.logger.info(f"Rejected after content analysis: {url} ({verified_confidence:.2f})")
                    except Exception as e:
                        self.logger.warning(f"Error analyzing profile content: {str(e)}")
                        # Fall back to original confidence
                        if confidence > 0.6:
                            result[platform] = url
                            self.logger.info(f"Using original confidence for {platform}: {url} ({confidence:.2f})")
                # For lower confidence, use if it's the best we have
                elif confidence > 0.6:
                    result[platform] = url
                    self.logger.info(f"Medium confidence match for {platform}: {url} ({confidence:.2f})")
        
        # Log results
        found_items = {k: v for k, v in result.items() if v is not None}
        if found_items:
            self.success_logger.info(f"AI search found for {full_name}: {found_items}")
        
        return result
    
    def _traditional_search(self, first_name: str, last_name: str, platforms: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Perform traditional search for athlete profiles (legacy method)."""
        full_name = f"{first_name} {last_name}"
        result = {
            "email": None,
            "phone": None,
            "twitter": None,
            "facebook": None,
            "instagram": None
        }
        
        context_keywords = ["athlete", "college", "sports"]  # Simplified, broader keywords
        name_parts = [first_name.lower(), last_name.lower()]

        # Social media searches with flexible, broader queries
        for domain, key in platforms.items():
            search_queries = [
                f"{full_name} {random.choice(context_keywords)} site:{domain}",  # No quotes
                f"{first_name} {last_name} {random.choice(context_keywords)} site:{domain}",  # No quotes
            ]
            for query in search_queries:
                html = self.search_platform(query, domain)
                if html:
                    links = self.extract_social_links(html, domain)
                    for link in links:
                        if any(part in link.lower() for part in name_parts):
                            result[key] = link
                            break
                    if not result[key] and links:
                        result[key] = links[0]
                    if result[key]:
                        break
                self.random_delay()

        # Contact info searches with broader queries
        contact_queries = [
            f"{full_name} {random.choice(context_keywords)} contact email phone",  # No quotes
            f"{first_name} {last_name} contact email",  # No quotes
        ]
        for query in contact_queries:
            html = self.search_platform(query, "")
            if html:
                emails = self.extract_emails(html)
                phones = self.extract_phones(html)
                for email in emails:
                    if any(part in email.lower() for part in name_parts) or any(kw in email.lower() for kw in ['edu', 'athletics']):
                        result["email"] = email
                        break
                if not result["email"] and emails:
                    result["email"] = emails[0]
                if phones:
                    result["phone"] = phones[0]
                if result["email"] or result["phone"]:
                    break
            self.random_delay()

        found_items = {k: v for k, v in result.items() if v is not None}
        if found_items:
            self.success_logger.info(f"Found for {full_name}: {found_items}")
        return result
    
    def fetch_profile_content(self, url: str) -> str:
        """Fetch the content of a profile page."""
        self.logger.info(f"Fetching profile content: {url}")
        try:
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Simulate human behavior
            self.simulate_human_behavior()
            
            # Scroll down to load more content
            self.driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(1)
            self.driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(1)
            
            # Get page source
            return self.driver.page_source
        except (TimeoutException, WebDriverException, NoSuchElementException) as e:
            self.logger.warning(f"Error fetching profile content: {str(e)}")
            return ""

    def extract_social_links(self, html: str, platform: str) -> List[str]:
        """Extract and clean social media URLs."""
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if platform in href:
                cleaned_url = self.clean_social_url(href, platform)
                if cleaned_url:
                    links.append(cleaned_url)
        return list(set(links))

    def clean_social_url(self, url: str, platform: str) -> Optional[str]:
        """Clean the URL to produce a base profile URL."""
        url = url.lower().strip()
        if '?' in url:
            url = url.split('?')[0]
        if platform == 'twitter.com':
            if any(x in url for x in ['/status/', '/likes/', '/retweets/']):
                return None
            match = re.search(r'twitter\.com/([^/]+)', url)
            if match:
                username = match.group(1)
                if username not in ['home', 'search', 'explore']:
                    return f'https://twitter.com/{username}'
        elif platform == 'facebook.com':
            if any(x in url for x in ['/posts/', '/photos/', '/videos/']):
                return None
            if 'profile.php?id=' in url:
                return url
            match = re.search(r'facebook\.com/([^/]+)', url)
            if match:
                username = match.group(1)
                if username not in ['public', 'pages', 'groups']:
                    return f'https://facebook.com/{username}'
        elif platform == 'instagram.com':
            if any(x in url for x in ['/p/', '/reel/', '/stories/']):
                return None
            match = re.search(r'instagram\.com/([^/]+)', url)
            if match:
                username = match.group(1)
                if username not in ['explore', 'direct', 'stories']:
                    return f'https://instagram.com/{username}'
        return None

    def extract_emails(self, html: str) -> List[str]:
        """Extract valid email addresses."""
        if not html:
            return []
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        emails = email_pattern.findall(html)
        valid_emails = []
        for email in set(emails):
            if self.is_valid_email(email):
                valid_emails.append(email.lower())
        return valid_emails

    def is_valid_email(self, email: str) -> bool:
        """Perform basic email validation."""
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return False
        disposable_domains = ['tempmail', 'throwaway', 'temporary']
        domain = email.split('@')[1].lower()
        if any(x in domain for x in disposable_domains):
            return False
        return True

    def extract_phones(self, html: str) -> List[str]:
        """Extract and format phone numbers."""
        if not html:
            return []
        phone_pattern = re.compile(r"""
            (?:\+?1[-.]?)?          # Optional country code
            (?:\s*\(?\d{3}\)?[-.\s]?)  # Area code
            \d{3}[-.\s]?            # First 3 digits
            \d{4}                   # Last 4 digits
            """, re.VERBOSE)
        phones = phone_pattern.findall(html)
        cleaned_phones = []
        for phone in set(phones):
            digits = re.sub(r'\D', '', phone)
            if len(digits) == 10:
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                cleaned_phones.append(formatted)
            elif len(digits) == 11 and digits.startswith('1'):
                formatted = f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
                cleaned_phones.append(formatted)
        return cleaned_phones
