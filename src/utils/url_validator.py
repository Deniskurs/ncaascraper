import re
import urllib.parse
from typing import Optional, Dict, List, Tuple
from bs4 import BeautifulSoup
from selenium import webdriver
import time

class URLValidator:
    """
    Enhanced URL validator for social media profiles.
    Provides improved filtering and validation of social media profile URLs.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the URL validator.
        
        Args:
            logger: Logger instance for logging
        """
        self.logger = logger
        
        # Define platform-specific patterns
        self.platform_patterns = {
            'twitter': {
                'valid_profile': r'^https?://(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)/?$',
                'invalid_paths': [
                    '/home', '/explore', '/notifications', '/messages', 
                    '/i', '/settings', '/compose', '/search', '/hashtag',
                    '/status/', '/lists/', '/topics/', '/bookmarks/'
                ],
                'profile_indicators': [
                    'Tweets', 'Followers', 'Following', 'Joined',
                    'profile-hover-card', 'profile-header'
                ]
            },
            'facebook': {
                'valid_profile': r'^https?://(?:www\.)?facebook\.com/(?:profile\.php\?id=\d+|[a-zA-Z0-9.]+)/?$',
                'invalid_paths': [
                    '/pages/', '/groups/', '/events/', '/marketplace/', 
                    '/watch/', '/gaming/', '/fundraisers/', '/offers/',
                    '/jobs/', '/weather/', '/recommendations/'
                ],
                'profile_indicators': [
                    'profile picture', 'cover photo', 'About', 'Friends',
                    'Photos', 'Videos', 'Timeline'
                ]
            },
            'instagram': {
                'valid_profile': r'^https?://(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)/?$',
                'invalid_paths': [
                    '/explore/', '/direct/', '/stories/', '/reels/',
                    '/tv/', '/shop/', '/accounts/', '/p/', '/reel/'
                ],
                'profile_indicators': [
                    'followers', 'following', 'posts', 'profile picture',
                    'bio', 'verified'
                ]
            }
        }
        
        # Define generic social media indicators
        self.generic_page_indicators = [
            'sign up', 'create account', 'join now', 'log in',
            'trending', 'popular', 'discover', 'explore',
            'terms of service', 'privacy policy', 'help center',
            'download app', 'app store', 'google play'
        ]
        
        # Define athlete profile indicators
        self.athlete_profile_indicators = [
            'athlete', 'player', 'team', 'sport', 'football',
            'basketball', 'baseball', 'soccer', 'ncaa', 'college',
            'university', 'roster', 'stats', 'statistics', 'highlights',
            'recruit', 'draft', 'scholarship'
        ]
    
    def clean_and_validate_url(self, url: str, platform: str) -> Optional[str]:
        """
        Clean and validate a social media URL.
        
        Args:
            url: The URL to clean and validate
            platform: The platform ('twitter', 'facebook', or 'instagram')
            
        Returns:
            Cleaned and validated URL, or None if invalid
        """
        if not url:
            return None
            
        # Normalize URL
        url = url.lower().strip()
        
        # Ensure URL has scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Parse URL
        parsed_url = urllib.parse.urlparse(url)
        
        # Extract domain
        domain = parsed_url.netloc
        if not domain:
            return None
            
        # Determine platform from domain if not specified
        if platform == '':
            if 'twitter.com' in domain:
                platform = 'twitter'
            elif 'facebook.com' in domain:
                platform = 'facebook'
            elif 'instagram.com' in domain:
                platform = 'instagram'
            else:
                return None
                
        # Get platform-specific patterns
        patterns = self.platform_patterns.get(platform)
        if not patterns:
            return None
            
        # Check for invalid paths
        path = parsed_url.path
        for invalid_path in patterns['invalid_paths']:
            if invalid_path in path:
                if self.logger:
                    self.logger.debug(f"Rejected URL with invalid path: {url}")
                return None
                
        # Check if URL matches valid profile pattern
        if re.match(patterns['valid_profile'], url):
            # Handle PHP endpoints for Facebook
            if platform == 'facebook' and '.php' in url:
                # Ensure it's a profile.php URL with an ID
                if not re.search(r'profile\.php\?id=\d+', url):
                    if self.logger:
                        self.logger.debug(f"Rejected invalid Facebook PHP URL: {url}")
                    return None
            
            # Clean URL by removing query parameters and fragments
            clean_url = self._clean_url(url, platform)
            
            if self.logger:
                self.logger.debug(f"Validated and cleaned URL: {clean_url}")
            return clean_url
        else:
            if self.logger:
                self.logger.debug(f"URL does not match valid profile pattern: {url}")
            return None
    
    def _clean_url(self, url: str, platform: str) -> str:
        """
        Clean a URL by removing query parameters and fragments.
        
        Args:
            url: The URL to clean
            platform: The platform ('twitter', 'facebook', or 'instagram')
            
        Returns:
            Cleaned URL
        """
        parsed_url = urllib.parse.urlparse(url)
        
        # Special handling for Facebook profile.php URLs
        if platform == 'facebook' and 'profile.php' in parsed_url.path:
            # Keep only the id parameter
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if 'id' in query_params:
                new_query = urllib.parse.urlencode({'id': query_params['id'][0]})
                return urllib.parse.urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    ''  # No fragment
                ))
        
        # For other URLs, remove query parameters and fragments
        return urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            '',  # No params
            '',  # No query
            ''   # No fragment
        ))
    
    def extract_username_from_url(self, url: str, platform: str) -> Optional[str]:
        """
        Extract username from a social media URL.
        
        Args:
            url: The URL to extract username from
            platform: The platform ('twitter', 'facebook', or 'instagram')
            
        Returns:
            Username or None if not found
        """
        if not url:
            return None
            
        # Get platform-specific pattern
        pattern = self.platform_patterns.get(platform, {}).get('valid_profile')
        if not pattern:
            return None
            
        # Extract username using regex
        match = re.match(pattern, url)
        if match and len(match.groups()) > 0:
            return match.group(1)
            
        # Special handling for Facebook profile.php URLs
        if platform == 'facebook' and 'profile.php' in url:
            match = re.search(r'id=(\d+)', url)
            if match:
                return f"profile_{match.group(1)}"
                
        return None
    
    def is_athlete_profile(self, url: str, platform: str, driver: webdriver.Chrome, athlete_name: str) -> Tuple[bool, float]:
        """
        Determine if a URL is likely an athlete profile by analyzing its content.
        
        Args:
            url: The URL to analyze
            platform: The platform ('twitter', 'facebook', or 'instagram')
            driver: Selenium WebDriver instance
            athlete_name: Name of the athlete to check for
            
        Returns:
            Tuple of (is_athlete_profile, confidence_score)
        """
        if not url or not driver:
            return False, 0.0
            
        try:
            # Navigate to the URL
            driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Get page source
            html = driver.page_source
            if not html:
                return False, 0.0
                
            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract text content
            text_content = soup.get_text().lower()
            
            # Check for generic page indicators
            generic_indicators_count = sum(1 for indicator in self.generic_page_indicators if indicator.lower() in text_content)
            
            # Check for athlete profile indicators
            athlete_indicators_count = sum(1 for indicator in self.athlete_profile_indicators if indicator.lower() in text_content)
            
            # Check for platform-specific profile indicators
            profile_indicators = self.platform_patterns.get(platform, {}).get('profile_indicators', [])
            profile_indicators_count = sum(1 for indicator in profile_indicators if indicator.lower() in text_content)
            
            # Check for athlete name
            name_parts = athlete_name.lower().split()
            name_parts_count = sum(1 for part in name_parts if part.lower() in text_content)
            
            # Calculate confidence score
            # More weight to profile indicators and athlete name
            confidence = (
                (profile_indicators_count / max(1, len(profile_indicators))) * 0.4 +
                (name_parts_count / max(1, len(name_parts))) * 0.3 +
                (athlete_indicators_count / max(1, len(self.athlete_profile_indicators))) * 0.2 -
                (generic_indicators_count / max(1, len(self.generic_page_indicators))) * 0.1
            )
            
            # Ensure confidence is between 0 and 1
            confidence = max(0.0, min(1.0, confidence))
            
            # Determine if it's an athlete profile
            is_athlete = confidence > 0.5
            
            if self.logger:
                self.logger.debug(f"URL {url} athlete profile analysis: {is_athlete} (confidence: {confidence:.2f})")
                
            return is_athlete, confidence
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error analyzing URL content: {str(e)}")
            return False, 0.0
    
    def filter_social_links(self, links: List[str], platform: str) -> List[str]:
        """
        Filter a list of social media links to keep only valid profile URLs.
        
        Args:
            links: List of URLs to filter
            platform: The platform ('twitter', 'facebook', or 'instagram')
            
        Returns:
            Filtered list of valid profile URLs
        """
        if not links:
            return []
            
        valid_links = []
        for link in links:
            clean_url = self.clean_and_validate_url(link, platform)
            if clean_url:
                valid_links.append(clean_url)
                
        # Remove duplicates
        valid_links = list(set(valid_links))
        
        if self.logger:
            self.logger.debug(f"Filtered {len(links)} links to {len(valid_links)} valid profile URLs for {platform}")
            
        return valid_links
    
    def is_valid_php_profile(self, url: str) -> bool:
        """
        Determine if a PHP URL is a valid profile page.
        
        Args:
            url: The URL to check
            
        Returns:
            Boolean indicating if it's a valid profile page
        """
        if not url or '.php' not in url:
            return False
            
        # Parse URL
        parsed_url = urllib.parse.urlparse(url)
        
        # Check for Facebook profile.php
        if 'facebook.com' in parsed_url.netloc and 'profile.php' in parsed_url.path:
            # Check for id parameter
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if 'id' in query_params and query_params['id'][0].isdigit():
                return True
                
        # Check for other common PHP profile patterns
        valid_php_patterns = [
            r'profile\.php\?id=\d+',
            r'user\.php\?id=\d+',
            r'member\.php\?id=\d+',
            r'athlete\.php\?id=\d+',
            r'player\.php\?id=\d+',
            r'roster\.php\?id=\d+'
        ]
        
        for pattern in valid_php_patterns:
            if re.search(pattern, url):
                return True
                
        return False
