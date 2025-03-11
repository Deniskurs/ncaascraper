import time
import random
import urllib.parse
import re
import json
import os
import base64
from datetime import datetime
import string
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from typing import Dict, Optional, List, Tuple, Any
from utils.url_validator import URLValidator
from utils.social_media_auth import SocialMediaAuth

class EnhancedScraperService:
    def __init__(self, driver, logger, success_logger, ai_verifier=None, vision_model='gpt-4o'):
        """Initialize the enhanced scraper service with AI verification capabilities."""
        self.driver = driver
        self.logger = logger
        self.success_logger = success_logger
        self.ai_verifier = ai_verifier
        self.search_engines = ['bing', 'duckduckgo']  # Start with Bing as it's more reliable
        self.current_engine = 0
        self.retry_count = 0
        self.max_retries = 3
        self.vision_enabled = False  # Vision is disabled by default
        self.vision_model = vision_model  # Model to use for vision verification
        self.active_learning = None  # Active learning component (optional)
        self.auth_handler = None  # Will be set when verify_login_before_scraping is called
        
        # Initialize URL validator
        self.url_validator = URLValidator(logger)
        
        # Create screenshot directory
        self.screenshot_dir = os.path.join("data", "screenshots")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
    
    def verify_login_before_scraping(self, auth_handler, platforms=None):
        """
        Verify login status before starting scraping and retry if necessary.
        
        Args:
            auth_handler: SocialMediaAuth instance
            platforms: List of platforms to verify login for
            
        Returns:
            Boolean indicating if all platforms are logged in
        """
        if platforms is None:
            platforms = ['twitter', 'facebook', 'instagram']
        
        self.auth_handler = auth_handler
        
        # Check login status for each platform
        all_logged_in = True
        for platform in platforms:
            if not auth_handler._check_login_status(platform, extended_check=True):
                self.logger.warning(f"Not logged in to {platform} before scraping, attempting login")
                all_logged_in = False
                
                # Navigate to platform homepage to check cookie consent
                if platform == 'twitter':
                    self.driver.get("https://twitter.com/")
                elif platform == 'facebook':
                    self.driver.get("https://www.facebook.com/")
                elif platform == 'instagram':
                    self.driver.get("https://www.instagram.com/")
                    
                # Handle cookie consent
                auth_handler.handle_cookie_consent(platform)
                
                # Attempt login
                success = False
                if platform == 'twitter':
                    success, _ = auth_handler.login_twitter()
                elif platform == 'facebook':
                    success, _ = auth_handler.login_facebook()
                elif platform == 'instagram':
                    success, _ = auth_handler.login_instagram()
                    
                if not success:
                    self.logger.error(f"Failed to login to {platform} before scraping")
                    return False
        
        return all_logged_in
    
    def verify_login_during_scraping(self, platform):
        """
        Verify login status during scraping and attempt to re-login if necessary.
        
        Args:
            platform: The platform to verify login for
            
        Returns:
            Boolean indicating if login was successful
        """
        if not self.auth_handler:
            self.logger.warning("No auth handler available for login verification")
            return False
            
        # Check if we're still logged in
        if self.auth_handler._check_login_status(platform):
            return True
            
        self.logger.warning(f"Session expired for {platform} during scraping, attempting to re-login")
        
        # Handle cookie consent
        self.auth_handler.handle_cookie_consent(platform)
        
        # Attempt login
        success = False
        if platform == 'twitter':
            success, _ = self.auth_handler.login_twitter()
        elif platform == 'facebook':
            success, _ = self.auth_handler.login_facebook()
        elif platform == 'instagram':
            success, _ = self.auth_handler.login_instagram()
            
        if not success:
            self.logger.error(f"Failed to re-login to {platform} during scraping")
            return False
            
        return True
    
    def get_profile_info(self, first_name: str, last_name: str, context: Dict[str, Any] = None) -> Dict[str, Optional[str]]:
        """Retrieve profile info using enhanced AI-driven search and verification."""
        full_name = f"{first_name} {last_name}"
        self.logger.info(f"Searching for {full_name} with enhanced pipeline")
        
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
        
        # If we don't have much context, try to acquire it dynamically
        if not context or (not context.get('School') and not context.get('Position')):
            state = context.get('State') if context else None
            acquired_context = self._acquire_dynamic_context(first_name, last_name, state)
            
            # Only update with acquired context if we found something useful
            if acquired_context.get("confidence", 0) > 0.2:
                self.logger.info(f"Acquired dynamic context for {full_name}: {acquired_context}")
                athlete_info.update(acquired_context)
        
        # Define platform mapping
        platforms = {
            "twitter.com": "twitter",
            "facebook.com": "facebook",
            "instagram.com": "instagram"
        }
        
        # Ensure we're logged in to all platforms before starting
        if self.auth_handler:
            self.verify_login_before_scraping(self.auth_handler, list(platforms.values()))
        
        # Use enhanced AI-driven search if available
        if self.ai_verifier:
            self.logger.info(f"Using enhanced AI-driven search for {full_name}")
            return self._enhanced_ai_search(athlete_info, platforms)
        else:
            # Fall back to traditional search
            self.logger.info(f"Using traditional search for {full_name} (AI verifier not available)")
            return self._traditional_search(first_name, last_name, platforms)
    
    def search_platform(self, query: str, domain: str, wait_time: int = 10) -> str:
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
                
                # Build and perform the search
                engine = self.search_engines[self.current_engine]
                self.logger.info(f"Searching {engine} for: {query}")
                
                if engine == 'bing':
                    url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"
                elif engine == 'duckduckgo':
                    url = f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}"
                else:
                    self.logger.error(f"Unknown search engine: {engine}")
                    return None
                
                self.driver.get(url)
                time.sleep(2)  # Wait for page to load
                
                # Get page source
                html = self.driver.page_source
                
                # Check if we got a valid response
                if "No results found" in html or "did not match any documents" in html:
                    self.logger.warning(f"No results found for query: {query}")
                    return None
                
                return html
            except Exception as e:
                self.logger.error(f"Error searching {engine}: {str(e)}")
                
                # Try next search engine
                self.current_engine = (self.current_engine + 1) % len(self.search_engines)
                self.retry_count += 1
                
                if self.retry_count < self.max_retries:
                    self.logger.info(f"Retrying with {self.search_engines[self.current_engine]}")
                    return self.search_platform(query, domain)
                else:
                    self.logger.error(f"Max retries reached for query: {query}")
                    self.retry_count = 0
                    return None
    
    def random_delay(self):
        """Introduce a random delay to avoid detection."""
        delay = random.uniform(1.0, 3.0)
        time.sleep(delay)
    
    def _acquire_dynamic_context(self, first_name: str, last_name: str, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Attempt to dynamically acquire NCAA context for an athlete.
        
        Args:
            first_name: Athlete's first name
            last_name: Athlete's last name
            state: Optional state information
            
        Returns:
            Dictionary with acquired context and confidence score
        """
        full_name = f"{first_name} {last_name}"
        self.logger.info(f"Acquiring NCAA context for {full_name}")
        
        # Try context-gathering searches
        context_queries = [
            f"{full_name} ncaa football player",
            f"{full_name} college football {state if state else ''}",
            f"{full_name} football roster"
        ]
        
        # Initialize context
        acquired_context = {
            "First_Name": first_name,
            "Last_Name": last_name,
            "State": state,
            "Sport": "football",  # We know we're looking for football players
            "confidence": 0.0
        }
        
        # Run context-gathering searches
        for query in context_queries:
            html = self.search_platform(query, "")
            if not html:
                continue
                
            # Use AI to extract potential context
            if self.ai_verifier:
                try:
                    # Extract text from HTML
                    soup = BeautifulSoup(html, 'html.parser')
                    extracted_text = soup.get_text()[:3000]  # Limit content length
                    
                    # Create a prompt for context extraction
                    prompt = f"""
                    Extract NCAA football player context information from these search results for {full_name}.
                    
                    SEARCH RESULTS:
                    {extracted_text}
                    
                    Extract the following information if present:
                    1. School/University name
                    2. Position played
                    3. Team name
                    4. Year (freshman, sophomore, junior, senior)
                    5. Jersey number
                    6. Any notable achievements or statistics
                    
                    Format your response as JSON with this structure:
                    {{
                        "school": "school name or null if not found",
                        "position": "position or null if not found",
                        "team": "team name or null if not found",
                        "year": "year or null if not found",
                        "jersey_number": "number or null if not found",
                        "achievements": ["achievement 1", "achievement 2", ...],
                        "confidence": 0-100
                    }}
                    
                    Base the confidence score (0-100) on how certain you are that this information refers to {full_name} as an NCAA football player.
                    """
                    
                    # Get AI response
                    system_instruction = "You are an expert at extracting NCAA football player information from search results."
                    
                    # Set up completion parameters
                    completion_params = {
                        "model": self.ai_verifier.model,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ]
                    }
                    
                    # Only add response_format if not using o1-preview
                    if not self.ai_verifier.model.startswith("o1-"):
                        completion_params["response_format"] = {"type": "json_object"}
                        completion_params["temperature"] = 0.2
                        
                    completion = self.ai_verifier.client.chat.completions.create(**completion_params)
                    
                    # Get the response content
                    response_content = completion.choices[0].message.content
                    
                    # Parse the response
                    try:
                        context_results = json.loads(response_content)
                        
                        # Update context if found with confidence weighting
                        ai_confidence = context_results.get("confidence", 0) / 100.0
                        
                        # Only update if we have some confidence
                        if ai_confidence > 0.3:
                            # Update school if found
                            if context_results.get("school"):
                                acquired_context["School"] = context_results["school"]
                                acquired_context["confidence"] += 0.2 * ai_confidence
                                
                            # Update position if found
                            if context_results.get("position"):
                                acquired_context["Position"] = context_results["position"]
                                acquired_context["confidence"] += 0.1 * ai_confidence
                                
                            # Update team if found
                            if context_results.get("team"):
                                acquired_context["Team"] = context_results["team"]
                                acquired_context["confidence"] += 0.1 * ai_confidence
                                
                            # Update year if found
                            if context_results.get("year"):
                                acquired_context["Year"] = context_results["year"]
                                acquired_context["confidence"] += 0.1 * ai_confidence
                                
                            # Update jersey number if found
                            if context_results.get("jersey_number"):
                                acquired_context["Jersey"] = context_results["jersey_number"]
                                acquired_context["confidence"] += 0.1 * ai_confidence
                            
                            # If we have sufficient context, stop searching
                            if acquired_context["confidence"] >= 0.4:
                                break
                                
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to parse context extraction response for {full_name}")
                        
                except Exception as e:
                    self.logger.error(f"Error extracting context for {full_name}: {str(e)}")
                    
            self.random_delay()
        
        # Add NCAA-specific search keywords based on acquired context
        search_keywords = ['ncaa', 'athlete', 'college', 'football']
        
        if acquired_context.get("School"):
            search_keywords.append(acquired_context["School"].lower())
            
            # Try to extract team nickname/mascot
            if self.ai_verifier and acquired_context.get("School"):
                try:
                    prompt = f"""What is the team nickname/mascot for {acquired_context["School"]} football team? Respond with just the nickname/mascot."""
                    
                    completion = self.ai_verifier.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=50
                    )
                    
                    mascot = completion.choices[0].message.content.strip()
                    if mascot and len(mascot) < 30:  # Sanity check
                        acquired_context["Mascot"] = mascot
                        search_keywords.append(mascot.lower())
                        
                except Exception as e:
                    self.logger.debug(f"Error getting mascot: {str(e)}")
        
        if acquired_context.get("Position"):
            search_keywords.append(acquired_context["Position"].lower())
            
        if acquired_context.get("Team"):
            search_keywords.append(acquired_context["Team"].lower())
            
        # Add search keywords to context
        acquired_context["search_keywords"] = search_keywords
        
        # Generate username patterns based on acquired context
        username_patterns = [
            first_name.lower(),
            last_name.lower(),
            f"{first_name[0].lower()}{last_name.lower()}",  # jsmith
            f"{first_name.lower()}{last_name[0].lower()}",  # johns
            f"{first_name.lower()}.{last_name.lower()}",    # john.smith
            f"{first_name.lower()}_{last_name.lower()}"     # john_smith
        ]
        
        # Add jersey number to username patterns if available
        if acquired_context.get("Jersey"):
            jersey = acquired_context["Jersey"]
            username_patterns.extend([
                f"{first_name.lower()}{jersey}",
                f"{last_name.lower()}{jersey}",
                f"{first_name[0].lower()}{last_name.lower()}{jersey}"
            ])
            
        # Add school/team-based patterns if available
        if acquired_context.get("School"):
            school_abbr = ''.join(word[0] for word in acquired_context["School"].split())
            username_patterns.extend([
                f"{first_name.lower()}_{school_abbr.lower()}",
                f"{last_name.lower()}_{school_abbr.lower()}"
            ])
            
        # Add username patterns to context
        acquired_context["username_patterns"] = username_patterns
        
        self.logger.info(f"Acquired context for {full_name}: {acquired_context}")
        return acquired_context
    
    def _enhanced_ai_search(self, athlete_info: Dict[str, Any], platforms: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Perform enhanced AI-driven search with multi-stage verification."""
        full_name = f"{athlete_info['First_Name']} {athlete_info['Last_Name']}"
        result = {
            "email": None,
            "phone": None,
            "twitter": None,
            "facebook": None,
            "instagram": None
        }
        
        # Stage 1: Generate optimized search queries
        # Use active learning if available, otherwise use AI
        if self.active_learning:
            queries = self.active_learning.suggest_queries(athlete_info)
            self.logger.info(f"Active learning suggested {len(queries)} search queries for {full_name}")
            reasoning = "Queries suggested by active learning based on past performance"
        else:
            queries, reasoning = self.ai_verifier.generate_advanced_search_queries(athlete_info)
            self.logger.info(f"AI generated {len(queries)} search queries for {full_name}")
            self.logger.debug(f"Query reasoning: {reasoning[:200]}...")
        
        # Add NCAA-specific and official source queries
        ncaa_specific_queries = [
            f"{full_name} site:.edu athletics roster football",
            f"{full_name} ncaa.com football profile",
            f"{full_name} goffrogs.com roster"
        ]
        
        # Add school-specific query if available
        if athlete_info.get('School'):
            school = athlete_info.get('School')
            ncaa_specific_queries.append(f"{full_name} {school} athletics football roster")
            # Try to create a school domain query
            school_words = school.lower().split()
            if len(school_words) > 1:
                # Try to form a domain like "athletics.harvard.edu"
                domain = f"athletics.{school_words[-1]}.edu"
                ncaa_specific_queries.append(f"{full_name} site:{domain}")
        
        # Add position-specific query if available
        if athlete_info.get('Position'):
            position = athlete_info.get('Position')
            ncaa_specific_queries.append(f"{full_name} ncaa football {position}")
        
        # Add state-specific query if available
        if athlete_info.get('State'):
            state = athlete_info.get('State')
            ncaa_specific_queries.append(f"{full_name} {state} college football player")
        
        # Add these to the beginning of the queries list for priority
        queries = ncaa_specific_queries + queries
        
        # Track candidate profiles across all searches
        all_candidates = []
        
        # Stage 2: Execute searches and collect candidates
        for query in queries:
            self.logger.info(f"Executing query: {query}")
            
            # Perform general search
            html = self.search_platform(query, "")
            if html:
                # Let AI analyze the search results
                candidates = self.ai_verifier.analyze_search_results(html, athlete_info)
                
                # Add source credibility scoring
                for candidate in candidates:
                    url = candidate.get("url", "").lower()
                    
                    # Boost confidence for official sources
                    if '.edu' in url and any(term in url for term in ['athletics', 'sports', 'roster']):
                        candidate["confidence"] = min(0.9, candidate.get("confidence", 0) + 0.2)
                        candidate["source_credibility"] = "high"
                        candidate["reasoning"] += " | Official .edu athletics source"
                    elif 'ncaa.com' in url or 'goffrogs.com' in url:
                        candidate["confidence"] = min(0.9, candidate.get("confidence", 0) + 0.2)
                        candidate["source_credibility"] = "high"
                        candidate["reasoning"] += " | Official NCAA source"
                    elif any(term in url for term in ['roster', 'player', 'bio', 'profile']):
                        candidate["confidence"] = min(0.85, candidate.get("confidence", 0) + 0.1)
                        candidate["source_credibility"] = "medium"
                        candidate["reasoning"] += " | Player roster/profile page"
                    
                    # Penalize non-sports sites
                    if any(term in url for term in ['linkedin.com', 'indeed.com', 'career']):
                        candidate["confidence"] = max(0.1, candidate.get("confidence", 0) - 0.3)
                        candidate["reasoning"] += " | Likely professional profile (not sports)"
                
                all_candidates.extend(candidates)
                
                # Record query effectiveness if active learning is enabled
                if self.active_learning:
                    highest_confidence = max([c.get("confidence", 0) for c in candidates]) if candidates else 0
                    self.active_learning.record_query_effectiveness(
                        query, athlete_info, "", len(candidates), highest_confidence
                    )
                
                # Extract contact info directly as backup
                emails = self.extract_emails(html)
                phones = self.extract_phones(html)
                
                # Add emails and phones as candidates
                for email in emails:
                    # Check for .edu emails (higher confidence)
                    if email.lower().endswith('.edu'):
                        confidence = 0.7
                        reasoning = "Educational institution email found in search results"
                    else:
                        confidence = 0.5
                        reasoning = "Email found in search results"
                    
                    all_candidates.append({
                        "url": email,
                        "platform": "email",
                        "confidence": confidence,
                        "reasoning": reasoning
                    })
                
                for phone in phones:
                    all_candidates.append({
                        "url": phone,
                        "platform": "phone",
                        "confidence": 0.5,
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
                    
                    # Record query effectiveness if active learning is enabled
                    if self.active_learning:
                        highest_confidence = max([c.get("confidence", 0) for c in platform_candidates]) if platform_candidates else 0
                        self.active_learning.record_query_effectiveness(
                            platform_query, athlete_info, key, len(platform_candidates), highest_confidence
                        )
                    
                    # Also extract links directly as backup
                    links = self.extract_social_links(html, domain)
                    for link in links:
                        # Check if this link is already in candidates
                        if not any(c.get("url") == link for c in all_candidates):
                            all_candidates.append({
                                "url": link,
                                "platform": key,
                                "confidence": 0.4,
                                "reasoning": "Link extracted from platform-specific search"
                            })
                
                self.random_delay()
        
        # Stage 3: Group candidates by platform
        platform_candidates = {}
        for candidate in all_candidates:
            platform = candidate.get("platform")
            if platform and platform in result:
                if platform not in platform_candidates:
                    platform_candidates[platform] = []
                platform_candidates[platform].append(candidate)
        
        # Stage 4: Verify and select the best candidate for each platform
        verified_candidates = {}
        
        for platform, candidates in platform_candidates.items():
            # Sort by confidence
            sorted_candidates = sorted(candidates, key=lambda x: x.get("confidence", 0), reverse=True)
            
            if sorted_candidates:
                # Take top 3 candidates for verification
                top_candidates = sorted_candidates[:3]
                
                for candidate in top_candidates:
                    url = candidate.get("url")
                    initial_confidence = candidate.get("confidence", 0)
                    
                    # Skip low confidence candidates
                    if initial_confidence < 0.4:
                        continue
                    
                    # For social media platforms, try to capture screenshot and verify with vision if enabled
                    if platform in platforms.values() and self._is_social_media_url(url) and self.vision_enabled:
                        try:
                            # Capture screenshot for vision verification
                            screenshot_path = self._capture_profile_screenshot(url, athlete_info)
                            
                            if screenshot_path:
                                # Verify with vision
                                vision_match, vision_confidence, vision_reasoning = self._verify_with_vision(
                                    screenshot_path, athlete_info
                                )
                                
                                # Create profile data for AI verification
                                profile_data = {
                                    platform: url,
                                    "screenshot_analysis": vision_reasoning
                                }
                                
                                # Verify with AI
                                is_match, verified_confidence, reasoning = self.ai_verifier.verify_profile_match(
                                    athlete_info, profile_data, vision_confidence
                                )
                                
                                # Store verification result
                                verified_candidates[platform] = {
                                    "url": url,
                                    "confidence": verified_confidence,
                                    "reasoning": reasoning,
                                    "vision_verified": True
                                }
                                
                                # If high confidence, break early
                                if verified_confidence > 0.8:
                                    break
                            else:
                                # Fall back to text-only verification
                                profile_data = {platform: url}
                                is_match, verified_confidence, reasoning = self.ai_verifier.verify_profile_match(
                                    athlete_info, profile_data, initial_confidence
                                )
                                
                                # Store verification result if better than existing
                                if platform not in verified_candidates or verified_confidence > verified_candidates[platform]["confidence"]:
                                    verified_candidates[platform] = {
                                        "url": url,
                                        "confidence": verified_confidence,
                                        "reasoning": reasoning,
                                        "vision_verified": False
                                    }
                        except Exception as e:
                            self.logger.warning(f"Error verifying {platform} profile {url}: {str(e)}")
                            # Continue to next candidate
                    else:
                        # For email and phone, use text-only verification
                        profile_data = {platform: url}
                        is_match, verified_confidence, reasoning = self.ai_verifier.verify_profile_match(
                            athlete_info, profile_data, initial_confidence
                        )
                        
                        # Store verification result if better than existing
                        if platform not in verified_candidates or verified_confidence > verified_candidates[platform]["confidence"]:
                            verified_candidates[platform] = {
                                "url": url,
                                "confidence": verified_confidence,
                                "reasoning": reasoning,
                                "vision_verified": False
                            }
        
        # Stage 5: Final synthesis and decision
        for platform, verification in verified_candidates.items():
            confidence = verification.get("confidence", 0)
            url = verification.get("url")
            
            # Get confidence threshold (use active learning if available)
            threshold = 0.7  # Increased default threshold for higher accuracy
            if self.active_learning:
                threshold = self.active_learning.get_confidence_threshold(athlete_info, platform)
                self.logger.info(f"Using active learning threshold for {platform}: {threshold:.2f}")
            
            # Accept high confidence matches
            if confidence > 0.8:
                result[platform] = url
                self.logger.info(f"High confidence match for {platform}: {url} ({confidence:.2f})")
                
                # Record verification in active learning if available
                if self.active_learning:
                    self.active_learning.record_verification(athlete_info, platform, url, confidence, True)
                    
            # Accept medium confidence matches with vision verification
            elif confidence > threshold and verification.get("vision_verified", False):
                result[platform] = url
                self.logger.info(f"Medium confidence match with vision for {platform}: {url} ({confidence:.2f})")
                
                # Record verification in active learning if available
                if self.active_learning:
                    self.active_learning.record_verification(athlete_info, platform, url, confidence, True)
                    
            # Accept medium confidence matches for email/phone with .edu domain
            elif confidence > threshold and platform == "email" and url.lower().endswith('.edu'):
                result[platform] = url
                self.logger.info(f"Medium confidence .edu email match: {url} ({confidence:.2f})")
                
                # Record verification in active learning if available
                if self.active_learning:
                    self.active_learning.record_verification(athlete_info, platform, url, confidence, True)
                    
            # Accept medium confidence matches for email/phone
            elif confidence > threshold + 0.1 and platform in ["email", "phone"]:
                # Higher threshold for non-.edu emails
                result[platform] = url
                self.logger.info(f"Medium confidence match for {platform}: {url} ({confidence:.2f})")
                
                # Record verification in active learning if available
                if self.active_learning:
                    self.active_learning.record_verification(athlete_info, platform, url, confidence, True)
        
        # Log results
        found_items = {k: v for k, v in result.items() if v is not None}
        if found_items:
            self.success_logger.info(f"Enhanced AI search found for {full_name}: {found_items}")
        
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
    
    def _verify_with_vision(self, screenshot_path: str, athlete_info: Dict[str, Any]) -> Tuple[bool, float, str]:
        """Verify a profile screenshot using vision capabilities."""
        if not self.ai_verifier:
            return False, 0.0, "AI verifier not available"
        
        # Check if vision is enabled
        if not self.vision_enabled:
            return False, 0.0, "Vision verification not enabled"
        
        try:
            # Read the screenshot file
            with open(screenshot_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Create a prompt for vision analysis
            full_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
            prompt = f"""
            Analyze this social media profile screenshot and determine if it belongs to NCAA football player {full_name}.
            
            Look for:
            1. Name matches or similarities
            2. References to football, NCAA, college athletics
            3. School/university mentions matching {athlete_info.get('School', 'Unknown')}
            4. Photos of the athlete in uniform or at athletic events
            5. Bio information related to football or athletics
            6. Mentions of position {athlete_info.get('Position', 'Unknown')} or jersey number
            
            Provide a detailed analysis of what you see in the image and whether this appears to be the correct athlete's profile.
            """
            
            # Call the vision model with the configured model
            response = self.ai_verifier.client.chat.completions.create(
                model=self.vision_model,  # Use the configured vision model
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            # Get the response content
            vision_analysis = response.choices[0].message.content
            
            # Extract match decision and confidence from the analysis
            is_match = False
            confidence = 0.5  # Default confidence
            
            # Check for positive indicators
            positive_indicators = [
                "appears to be the correct athlete",
                "likely belongs to",
                "high confidence this is",
                "strong evidence this is",
                "profile matches",
                "confirmed match"
            ]
            
            # Check for negative indicators
            negative_indicators = [
                "does not appear to be",
                "unlikely to be",
                "no evidence this is",
                "cannot confirm this is",
                "different person",
                "not a match"
            ]
            
            # Determine match based on indicators
            if any(indicator in vision_analysis.lower() for indicator in positive_indicators):
                is_match = True
                confidence = 0.7  # Start with moderate confidence
                
                # Increase confidence for stronger matches
                if "confirmed match" in vision_analysis.lower() or "strong evidence" in vision_analysis.lower():
                    confidence = 0.85
            elif any(indicator in vision_analysis.lower() for indicator in negative_indicators):
                is_match = False
                confidence = 0.2  # Low confidence in non-match
                
                # Decrease confidence for stronger non-matches
                if "definitely not" in vision_analysis.lower() or "clearly not" in vision_analysis.lower():
                    confidence = 0.1
            
            # Return the results
            return is_match, confidence, vision_analysis
            
        except Exception as e:
            self.logger.error(f"Error in vision verification: {str(e)}")
            return False, 0.0, f"Vision verification error: {str(e)}"
    
    def _is_social_media_url(self, url: str) -> bool:
        """Check if a URL is a valid social media profile URL using enhanced validation."""
        if not url:
            return False
            
        # Check for email or phone
        if '@' in url or url.startswith('tel:') or re.match(r'^\d{3}[-.\s]?\d{3}[-.\s]?\d{4}$', url):
            return False
        
        # Determine platform from URL
        platform = ''
        if 'twitter.com' in url.lower():
            platform = 'twitter'
        elif 'facebook.com' in url.lower():
            platform = 'facebook'
        elif 'instagram.com' in url.lower():
            platform = 'instagram'
        else:
            return False
            
        # Use URL validator to validate the URL
        validated_url = self.url_validator.clean_and_validate_url(url, platform)
        
        # If URL validator returns a valid URL, it's a social media profile URL
        return validated_url is not None
    
    def _capture_profile_screenshot(self, url: str, athlete_info: Dict[str, Any]) -> Optional[str]:
        """Capture a screenshot of a social media profile for vision verification."""
        if not url or not self._is_social_media_url(url):
            return None
            
        try:
            # Generate a unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            filename = f"{athlete_info.get('First_Name', 'unknown')}_{athlete_info.get('Last_Name', 'unknown')}_{timestamp}_{random_str}.png"
            screenshot_path = os.path.join(self.screenshot_dir, filename)
            
            # Navigate to the URL
            self.logger.info(f"Capturing screenshot of {url}")
            self.driver.get(url)
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Scroll down slightly to show more content
                self.driver.execute_script("window.scrollBy(0, 300)")
                time.sleep(1)
                
                # Take screenshot
                self.driver.save_screenshot(screenshot_path)
                self.logger.info(f"Screenshot saved to {screenshot_path}")
                
                return screenshot_path
            except TimeoutException:
                self.logger.warning(f"Timeout waiting for page to load: {url}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error capturing screenshot: {str(e)}")
            return None
    
    def extract_social_links(self, html: str, domain: str) -> List[str]:
        """Extract and clean social media URLs using enhanced validation."""
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        raw_links = []
        
        # Extract all links from the HTML
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if domain in href:
                raw_links.append(href)
        
        # Determine platform from domain
        platform = ''
        if 'twitter.com' in domain:
            platform = 'twitter'
        elif 'facebook.com' in domain:
            platform = 'facebook'
        elif 'instagram.com' in domain:
            platform = 'instagram'
        
        # Use URL validator to filter and clean links
        valid_links = self.url_validator.filter_social_links(raw_links, platform)
        
        self.logger.debug(f"Extracted {len(raw_links)} links, {len(valid_links)} valid profile URLs for {domain}")
        return valid_links
    
    def clean_social_url(self, url: str, platform: str) -> Optional[str]:
        """Clean and validate a social media URL using enhanced validation."""
        # Determine platform string from domain
        platform_key = ''
        if 'twitter.com' in platform:
            platform_key = 'twitter'
        elif 'facebook.com' in platform:
            platform_key = 'facebook'
        elif 'instagram.com' in platform:
            platform_key = 'instagram'
        
        # Use URL validator to clean and validate the URL
        return self.url_validator.clean_and_validate_url(url, platform_key)
    
    def extract_emails(self, html: str) -> List[str]:
        """Extract valid email addresses."""
        if not html:
            return []
            
        # Use a comprehensive regex for email extraction
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        emails = email_pattern.findall(html)
        
        # Filter and validate emails
        valid_emails = []
        for email in set(emails):
            if self.is_valid_email(email):
                valid_emails.append(email.lower())
                
        return valid_emails
    
    def is_valid_email(self, email: str) -> bool:
        """Perform basic email validation."""
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return False
            
        # Check for disposable email domains
        disposable_domains = ['tempmail', 'throwaway', 'temporary', 'mailinator', 'guerrillamail']
        domain = email.split('@')[1].lower()
        
        if any(x in domain for x in disposable_domains):
            return False
            
        # Prioritize .edu emails
        if domain.endswith('.edu'):
            return True
            
        # Check for common email providers
        common_providers = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com']
        if domain in common_providers:
            return True
            
        # Additional validation for other domains
        return len(domain.split('.')) >= 2 and len(domain) >= 4
    
    def extract_phones(self, html: str) -> List[str]:
        """Extract and format phone numbers."""
        if not html:
            return []
            
        # Use a comprehensive regex for phone extraction
        phone_pattern = re.compile(r"""
            (?:\+?1[-.\s]?)?          # Optional country code
            (?:\s*\(?\d{3}\)?[-.\s]?)  # Area code
            \d{3}[-.\s]?            # First 3 digits
            \d{4}                   # Last 4 digits
            """, re.VERBOSE)
            
        phones = phone_pattern.findall(html)
        
        # Clean and format phone numbers
        cleaned_phones = []
        for phone in set(phones):
            # Extract only digits
            digits = re.sub(r'\D', '', phone)
            
            # Format 10-digit numbers
            if len(digits) == 10:
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                cleaned_phones.append(formatted)
            # Format 11-digit numbers starting with 1 (US country code)
            elif len(digits) == 11 and digits.startswith('1'):
                formatted = f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
                cleaned_phones.append(formatted)
                
        return cleaned_phones
    
    def fetch_profile_content(self, url: str) -> str:
        """Fetch the content of a profile page."""
        self.logger.info(f"Fetching profile content: {url}")
        
        try:
            # Determine platform from URL
            platform = None
            if 'twitter.com' in url.lower():
                platform = 'twitter'
            elif 'facebook.com' in url.lower():
                platform = 'facebook'
            elif 'instagram.com' in url.lower():
                platform = 'instagram'
            
            # Navigate to the URL
            self.driver.get(url)
            
            # Handle cookie consent if needed
            if platform and self.auth_handler:
                self.auth_handler.handle_cookie_consent(platform)
            
            # Verify login status if needed
            if platform and self.auth_handler:
                if not self.verify_login_during_scraping(platform):
                    self.logger.warning(f"Could not verify login for {platform}, content may be limited")
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Simulate human behavior
            self.driver.execute_script("window.scrollBy(0, 300)")
            time.sleep(1)
            self.driver.execute_script("window.scrollBy(0, 300)")
            time.sleep(1)
            
            # Get page source
            return self.driver.page_source
            
        except (TimeoutException, WebDriverException, NoSuchElementException) as e:
            self.logger.warning(f"Error fetching profile content: {str(e)}")
            return ""
