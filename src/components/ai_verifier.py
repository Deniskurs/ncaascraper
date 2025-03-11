from openai import OpenAI
import re
import json
import base64
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup

class AIVerifier:
    def __init__(self, api_key: str, logger=None, model="gpt-4o", search_query_model="gpt-4o"):
        """Initialize OpenAI client with provided API key."""
        self.client = OpenAI(api_key=api_key)
        self.logger = logger
        self.model = model  # Default to gpt-4o for verification and analysis
        self.search_query_model = search_query_model  # Default to gpt-4o for search query generation
        self.search_enabled = True
        self.cache_dir = os.path.join("data", "cache")
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        # Initialize caches
        self.query_cache = {}
        self.verification_cache = {}

    def verify_profile_match(self, 
                          athlete_info: Dict[str, Any], 
                          profile_data: Dict[str, Any], 
                          confidence_score: float = 0.0) -> Tuple[bool, float, str]:
        """
        Enhanced multi-stage verification to determine if the profile belongs to the correct NCAA athlete.
        
        Args:
            athlete_info: Dict containing athlete information
            profile_data: Dict containing profile information
            confidence_score: Initial confidence score
            
        Returns:
            Tuple of (is_match, adjusted_confidence, reasoning)
        """
        athlete_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
        state = athlete_info.get('State', '')
        
        # Create cache key
        cache_key = f"{athlete_name}_{hash(json.dumps(profile_data, sort_keys=True))}"
        
        # Check cache
        if cache_key in self.verification_cache:
            self.logger.info(f"Using cached verification for {athlete_name}")
            return self.verification_cache[cache_key]
        
        if self.logger:
            self.logger.info(f"Performing multi-stage verification for {athlete_name} using {self.model}")
        
        try:
            # STAGE 1: Determine if this is an NCAA football player at all
            is_ncaa_player, ncaa_confidence, ncaa_reasoning = self._determine_ncaa_status(profile_data, athlete_name)
            
            if not is_ncaa_player and ncaa_confidence > 0.6:
                # If we're confident this isn't an NCAA player, reject immediately
                result_tuple = (False, 0.1, f"Not an NCAA football player: {ncaa_reasoning}")
                self.verification_cache[cache_key] = result_tuple
                return result_tuple
            
            # STAGE 2: Check if this specific NCAA player matches our target
            is_match, match_confidence, match_reasoning = self._verify_specific_player_match(
                athlete_info, profile_data, ncaa_confidence
            )
            
            # STAGE 3: Check for disqualifying evidence
            has_disqualifiers, disqualifier_confidence, disqualifier_reasoning = (
                self._check_disqualifying_evidence(athlete_info, profile_data)
            )
            
            if has_disqualifiers and disqualifier_confidence > 0.7:
                # Strong disqualifying evidence overrides potential matches
                result_tuple = (False, 0.1, f"Disqualified: {disqualifier_reasoning}")
                self.verification_cache[cache_key] = result_tuple
                return result_tuple
            
            # Final decision with detailed reasoning
            combined_reasoning = f"NCAA Status: {ncaa_reasoning}\n\nMatch Analysis: {match_reasoning}"
            if has_disqualifiers:
                combined_reasoning += f"\n\nPotential Disqualifiers: {disqualifier_reasoning}"
            
            # Cache the result
            result_tuple = (is_match, match_confidence, combined_reasoning)
            self.verification_cache[cache_key] = result_tuple
            
            if self.logger:
                self.logger.info(f"Multi-stage verification for {athlete_name}: {is_match}, confidence: {match_confidence:.2f}")
            
            return result_tuple
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in multi-stage verification for {athlete_name}: {str(e)}")
            # Fall back to original confidence score
            return confidence_score > 0.6, confidence_score, f"Verification failed: {str(e)}"
            
    def generate_advanced_search_queries(self, athlete_info: Dict[str, Any]) -> Tuple[List[str], str]:
        """
        Generate highly specific search queries using AI reasoning.
        
        Args:
            athlete_info: Dict containing athlete information
            
        Returns:
            Tuple of (list of search queries, reasoning behind queries)
        """
        athlete_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
        
        # Create cache key
        cache_key = f"queries_{athlete_name}_{athlete_info.get('School', '')}_{athlete_info.get('Sport', '')}"
        
        # Check cache
        if cache_key in self.query_cache:
            self.logger.info(f"Using cached search queries for {athlete_name}")
            return self.query_cache[cache_key]
        
        if self.logger:
            self.logger.info(f"Generating search queries for {athlete_name} using {self.search_query_model}")
        
        try:
            # Create a detailed prompt for the AI
            prompt = f"""
            Generate 5 highly specific and varied search queries to find social media profiles and contact information for this NCAA athlete:
            
            ATHLETE INFO:
            - Name: {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}
            - Sport: {athlete_info.get('Sport', 'Unknown')}
            - School/College: {athlete_info.get('School', 'Unknown')}
            - Position: {athlete_info.get('Position', 'Unknown')}
            - Year: {athlete_info.get('Year', 'Unknown')}
            
            Create a mix of different query types:
            1. One query with the full name WITHOUT quotes (e.g., John Smith NCAA athlete)
            2. One query with the name in quotes (e.g., "John Smith" college football)
            3. One query using site-specific search (e.g., John Smith site:twitter.com)
            4. One query with school and sport information (e.g., John Smith Harvard basketball)
            5. One query with potential username patterns (e.g., jsmith OR johnsmith NCAA)
            
            Consider these elements:
            1. School-specific terminology (team names, mascots)
            2. Sport-specific terms and statistics relevant to their position
            3. Likely username patterns for this specific athlete
            4. NCAA-specific identifiers
            5. Advanced search operators to narrow results
            
            For each query, explain your reasoning for why this query would be effective for this specific athlete.
            
            IMPORTANT: Format your response as valid, parseable JSON with this exact structure:
            {{
                "queries": [
                    {{
                        "query": "the search query text",
                        "reasoning": "explanation of why this query is effective"
                    }},
                    ...
                ]
            }}
            
            Ensure your response is properly formatted JSON that can be parsed with json.loads().
            """
            
            system_instruction = "You are an expert at finding NCAA athletes online. Generate search queries that will specifically identify this athlete and distinguish them from others with similar names."
            enhanced_prompt = f"{system_instruction}\n\n{prompt}"
            
            # Set up completion parameters
            completion_params = {
                "model": self.search_query_model,
                "messages": [
                    {"role": "user", "content": enhanced_prompt}
                ]
            }
            
            # Only add response_format if not using o1-preview
            if not self.search_query_model.startswith("o1-"):
                completion_params["response_format"] = {"type": "json_object"}
            
            # Only add temperature if not using o1-preview
            if not self.search_query_model.startswith("o1-"):
                completion_params["temperature"] = 0.4
                
            completion = self.client.chat.completions.create(**completion_params)
            
            # Log token usage (reasoning tokens only available for o1-preview)
            if self.search_query_model.startswith("o1-") and hasattr(completion, 'usage') and hasattr(completion.usage, 'completion_tokens_details'):
                reasoning_tokens = getattr(completion.usage.completion_tokens_details, 'reasoning_tokens', 0)
                self.logger.info(f"Used {reasoning_tokens} reasoning tokens for query generation")
            elif hasattr(completion, 'usage'):
                self.logger.info(f"Used {completion.usage.completion_tokens} completion tokens for query generation")
            
            # Get the response content
            response_content = completion.choices[0].message.content
            
            # Try to parse as JSON first
            try:
                response_data = json.loads(response_content)
                queries = [item["query"] for item in response_data.get("queries", [])]
                reasoning = "\n".join([f"Query: {item['query']}\nReasoning: {item['reasoning']}" 
                                     for item in response_data.get("queries", [])])
            except json.JSONDecodeError:
                # If JSON parsing fails, extract queries using regex
                self.logger.warning(f"JSON parsing failed, using regex extraction for queries for {athlete_name}")
                # Simple extraction: look for lines that might be queries
                lines = response_content.split('\n')
                queries = []
                reasoning = "Queries extracted from text response:\n"
                
                for line in lines:
                    # Look for lines that might be search queries (not too long, no special formatting)
                    if 5 < len(line.strip()) < 100 and not line.startswith('#') and not line.startswith('*'):
                        if any(term in line.lower() for term in [athlete_info.get('First_Name', '').lower(), 
                                                               athlete_info.get('Last_Name', '').lower(), 
                                                               'ncaa', 'athlete', 'college', 
                                                               athlete_info.get('Sport', '').lower()]):
                            queries.append(line.strip())
                            reasoning += f"- {line.strip()}\n"
                
                # If we couldn't extract any queries, use fallbacks
                if not queries:
                    queries = [
                        f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')} {athlete_info.get('School', '')} {athlete_info.get('Sport', '')}",
                        f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')} NCAA athlete"
                    ]
                    reasoning += "Using fallback queries due to parsing failure."
            
            # Filter out empty queries and limit to 5
            valid_queries = [q for q in queries if q][:5]
            
            if self.logger:
                self.logger.info(f"Generated {len(valid_queries)} search queries for {athlete_name}")
            
            # Cache the result
            result_tuple = (valid_queries, reasoning)
            self.query_cache[cache_key] = result_tuple
            
            return result_tuple
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error generating search queries for {athlete_name}: {str(e)}")
            # Return basic fallback queries
            fallback_queries = [
                f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')} {athlete_info.get('School', '')} {athlete_info.get('Sport', '')}",
                f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')} NCAA athlete"
            ]
            return fallback_queries, f"Error generating queries: {str(e)}"
    
    def suggest_search_queries(self, athlete_info: Dict[str, Any]) -> List[str]:
        """
        Generate additional search queries for an athlete using AI (legacy method).
        
        Args:
            athlete_info: Dict containing athlete information
            
        Returns:
            List of suggested search queries
        """
        queries, _ = self.generate_advanced_search_queries(athlete_info)
        return queries[:3]  # Limit to 3 for backward compatibility
    
    def analyze_search_results(self, 
                              search_results: str, 
                              athlete_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze search results using AI reasoning.
        
        Args:
            search_results: HTML content of search results
            athlete_info: Dict containing athlete information
            
        Returns:
            List of candidate profiles with confidence scores and reasoning
        """
        athlete_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
        if self.logger:
            self.logger.info(f"Analyzing search results for {athlete_name} with {self.model}")
        
        try:
            # Extract text and links from search results
            soup = BeautifulSoup(search_results, 'html.parser')
            
            # Extract text (limit length)
            extracted_text = soup.get_text()[:3000]
            
            # Extract links
            extracted_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(domain in href for domain in ['twitter.com', 'facebook.com', 'instagram.com', '.edu']):
                    extracted_links.append(href)
            
            # Limit number of links
            extracted_links = extracted_links[:20]
            
            # Create a prompt for the AI
            prompt = f"""
            Analyze these search results to identify links that are most likely to be the social media profiles or contact information for this NCAA athlete:
            
            ATHLETE INFO:
            - Name: {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}
            - Sport: {athlete_info.get('Sport', 'Unknown')}
            - School/College: {athlete_info.get('School', 'Unknown')}
            - Position: {athlete_info.get('Position', 'Unknown')}
            - Year: {athlete_info.get('Year', 'Unknown')}
            
            SEARCH RESULTS TEXT:
            {extracted_text}
            
            EXTRACTED LINKS:
            {', '.join(extracted_links)}
            
            For each link that might be relevant, explain:
            1. Why you think this link might be for the correct athlete
            2. What specific evidence in the search results supports this
            3. Your confidence level (0-100%)
            4. Any additional context that would help verify this link
            
            Be especially careful to distinguish this athlete from others with similar names.
            
            IMPORTANT: Format your response as valid, parseable JSON with this exact structure:
            {{
                "candidate_profiles": [
                    {{
                        "url": "the profile URL",
                        "platform": "twitter/facebook/instagram/email/phone/other",
                        "confidence": 85,
                        "reasoning": "detailed explanation of why this is likely the correct athlete"
                    }},
                    ...
                ]
            }}
            
            Ensure your response is properly formatted JSON that can be parsed with json.loads().
            """
            
            # Get AI response
            system_instruction = "You are an expert at identifying NCAA athletes in search results. Analyze these results to find the most likely matches for the specified athlete."
            enhanced_prompt = f"{system_instruction}\n\n{prompt}"
            
            # Set up completion parameters
            completion_params = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": enhanced_prompt}
                ]
            }
            
            # Only add response_format if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["response_format"] = {"type": "json_object"}
            
            # Only add temperature if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["temperature"] = 0.2
                
            completion = self.client.chat.completions.create(**completion_params)
            
            # Log token usage (reasoning tokens only available for o1-preview)
            if self.model.startswith("o1-") and hasattr(completion, 'usage') and hasattr(completion.usage, 'completion_tokens_details'):
                reasoning_tokens = getattr(completion.usage.completion_tokens_details, 'reasoning_tokens', 0)
                self.logger.info(f"Used {reasoning_tokens} reasoning tokens for search analysis")
            elif hasattr(completion, 'usage'):
                self.logger.info(f"Used {completion.usage.completion_tokens} completion tokens for search analysis")
            
            # Get the response content
            response_content = completion.choices[0].message.content
            
            # Try to parse as JSON first
            try:
                response_data = json.loads(response_content)
                candidates = response_data.get("candidate_profiles", [])
                
                # Convert confidence from percentage to decimal
                for candidate in candidates:
                    if "confidence" in candidate:
                        candidate["confidence"] = candidate["confidence"] / 100.0
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract information using regex and direct HTML parsing
                self.logger.warning(f"JSON parsing failed, using direct extraction for search results for {athlete_name}")
                candidates = []
                
                # First try to extract URLs from the AI response
                url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
                urls_from_response = re.findall(url_pattern, response_content)
                
                # Then extract URLs directly from the HTML
                urls_from_html = []
                if soup:
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        if any(domain in href.lower() for domain in ['twitter.com', 'facebook.com', 'instagram.com', '.edu']):
                            urls_from_html.append(href)
                
                # Combine and deduplicate URLs
                all_urls = list(set(urls_from_response + urls_from_html))
                
                # Filter and clean URLs before processing
                filtered_urls = []
                for url in all_urls:
                    # Skip URLs that are clearly not profiles
                    if any(x in url.lower() for x in [
                        '/search', '/explore', '/hashtag/', '/trending', 
                        '/settings', '/privacy', '/help', '/about',
                        '/terms', '/cookies', '/ads', '/business',
                        '/status/', '/posts/', '/photos/', '/videos/',
                        '/p/', '/reel/', '/stories/'
                    ]):
                        continue
                    
                    # Clean the URL
                    cleaned_url = url.split('?')[0]  # Remove query parameters
                    filtered_urls.append(cleaned_url)
                
                # Remove duplicates
                filtered_urls = list(set(filtered_urls))
                
                # For each URL found, create a candidate profile
                for url in filtered_urls:
                    # Extract username from URL for social media platforms using platform-specific extractors
                    username = None
                    if 'twitter.com' in url.lower():
                        username = self._extract_twitter_username(url)
                    elif 'facebook.com' in url.lower():
                        username = self._extract_facebook_username(url)
                    elif 'instagram.com' in url.lower():
                        username = self._extract_instagram_username(url)
                    
                    # Skip common non-profile usernames
                    if username and username.lower() in [
                        'home', 'search', 'explore', 'notifications', 'messages',
                        'bookmarks', 'lists', 'profile', 'public', 'pages', 'groups'
                    ]:
                        continue
                    
                    # Check if URL or username contains athlete name parts
                    first_name = athlete_info.get('First_Name', '').lower()
                    last_name = athlete_info.get('Last_Name', '').lower()
                    
                    # Calculate initial confidence based on name match
                    initial_confidence = 0.4  # Base confidence
                    
                    # Check for exact name matches in username
                    if username:
                        username_lower = username.lower()
                        
                        # Check for exact matches (e.g., johnsmith, john_smith)
                        if f"{first_name}{last_name}" in username_lower.replace('_', '').replace('.', ''):
                            initial_confidence = 0.7
                        # Check for first initial + last name (e.g., jsmith)
                        elif first_name[0] + last_name in username_lower.replace('_', '').replace('.', ''):
                            initial_confidence = 0.65
                        # Check for first name + last initial (e.g., johns)
                        elif first_name + last_name[0] in username_lower.replace('_', '').replace('.', ''):
                            initial_confidence = 0.65
                        # Check for partial name matches
                        elif first_name in username_lower or last_name in username_lower:
                            initial_confidence = 0.6
                    
                    # If no username match, check URL
                    elif first_name in url.lower() or last_name in url.lower():
                        initial_confidence = 0.55
                    
                    # Determine platform
                    if 'twitter.com' in url.lower():
                        platform = 'twitter'
                    elif 'facebook.com' in url.lower():
                        platform = 'facebook'
                    elif 'instagram.com' in url.lower():
                        platform = 'instagram'
                    elif '.edu' in url.lower():
                        platform = 'school'
                        # Higher confidence for .edu URLs with athletics or sports
                        if any(x in url.lower() for x in ['athletics', 'sports', 'roster', 'team']):
                            initial_confidence = 0.6
                        else:
                            initial_confidence = 0.5
                    else:
                        platform = 'other'
                    
                    # Check for additional context that might increase confidence
                    school = athlete_info.get('School', '').lower()
                    sport = athlete_info.get('Sport', '').lower()
                    position = athlete_info.get('Position', '').lower()
                    
                    # School name in URL or username
                    if school and (school in url.lower() or (username and school in username.lower())):
                        initial_confidence += 0.1
                    
                    # Sport in URL
                    if sport and sport in url.lower():
                        initial_confidence += 0.1
                    
                    # Position in URL
                    if position and position in url.lower():
                        initial_confidence += 0.05
                    
                    # NCAA or college athletics keywords
                    if any(x in url.lower() for x in ['ncaa', 'college', 'athletics', 'roster']):
                        initial_confidence += 0.1
                    
                    # Cap confidence at 0.85 for direct extraction
                    initial_confidence = min(0.85, initial_confidence)
                    
                    # Create reasoning based on matches
                    reasoning_parts = [f"URL extracted directly from search results: {url}"]
                    if username:
                        reasoning_parts.append(f"Username: {username}")
                    if first_name in url.lower() or last_name in url.lower() or (username and (first_name in username.lower() or last_name in username.lower())):
                        reasoning_parts.append("Contains athlete name")
                    if school and (school in url.lower() or (username and school in username.lower())):
                        reasoning_parts.append(f"Contains school: {school}")
                    if sport and sport in url.lower():
                        reasoning_parts.append(f"Contains sport: {sport}")
                    
                    # Create a candidate profile
                    candidates.append({
                        "url": url,
                        "platform": platform,
                        "confidence": initial_confidence,
                        "reasoning": " | ".join(reasoning_parts)
                    })
            
            if self.logger:
                self.logger.info(f"{self.model} identified {len(candidates)} candidate profiles for {athlete_name}")
            
            return candidates
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error analyzing search results for {athlete_name}: {str(e)}")
            return []
    
    def analyze_profile_content(self, 
                               profile_url: str, 
                               profile_content: str, 
                               athlete_info: Dict[str, Any], 
                               confidence_score: float = 0.0) -> Tuple[bool, float, str]:
        """
        Analyze the content of a profile page to verify if it belongs to the correct athlete.
        
        Args:
            profile_url: URL of the profile
            profile_content: HTML or text content of the profile
            athlete_info: Dict containing athlete information
            
        Returns:
            Tuple of (is_match, confidence, reasoning)
        """
        athlete_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
        if self.logger:
            self.logger.info(f"AI analyzing profile content for {athlete_name}: {profile_url}")
        
        try:
            # Extract text from HTML if needed
            if '<html' in profile_content.lower():
                soup = BeautifulSoup(profile_content, 'html.parser')
                extracted_content = soup.get_text()[:3000]  # Limit content length
            else:
                extracted_content = profile_content[:3000]
            
            # Create a prompt for the AI
            prompt = f"""
            Analyze this profile content to determine if it belongs to the specified NCAA athlete:
            
            ATHLETE INFO:
            - Name: {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}
            - Sport: {athlete_info.get('Sport', 'Unknown')}
            - School/College: {athlete_info.get('School', 'Unknown')}
            - Position: {athlete_info.get('Position', 'Unknown')}
            - Year: {athlete_info.get('Year', 'Unknown')}
            
            PROFILE URL:
            {profile_url}
            
            PROFILE CONTENT:
            {extracted_content}
            
            Analyze this profile by considering:
            1. Does the profile explicitly mention the athlete's name?
            2. Does it reference their school or team?
            3. Does it mention their sport or position?
            4. Are there references to NCAA, college athletics, or similar terms?
            5. Does the profile's activity/content align with what you'd expect from a college athlete?
            6. Are there any red flags suggesting this is NOT the correct athlete?
            
            IMPORTANT: Format your response as valid, parseable JSON with this exact structure:
            {{
                "is_match": true/false,
                "confidence": 85,
                "reasoning": "detailed explanation of your analysis and conclusion",
                "key_evidence": ["specific piece of evidence 1", "specific piece of evidence 2", ...],
                "contradictory_evidence": ["contradictory evidence 1", "contradictory evidence 2", ...]
            }}
            
            Ensure your response is properly formatted JSON that can be parsed with json.loads().
            """
            
            # Get AI response
            system_instruction = "You are an expert at verifying NCAA athlete profiles. Determine if this profile belongs to the specified athlete."
            enhanced_prompt = f"{system_instruction}\n\n{prompt}"
            
            # Set up completion parameters
            completion_params = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": enhanced_prompt}
                ],
                "store": True
            }
            
            # Only add response_format if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["response_format"] = {"type": "json_object"}
            
            # Only add temperature if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["temperature"] = 0.2
                
            completion = self.client.chat.completions.create(**completion_params)
            
            # Log token usage (reasoning tokens only available for o1-preview)
            if self.model.startswith("o1-") and hasattr(completion, 'usage') and hasattr(completion.usage, 'completion_tokens_details'):
                reasoning_tokens = getattr(completion.usage.completion_tokens_details, 'reasoning_tokens', 0)
                self.logger.info(f"Used {reasoning_tokens} reasoning tokens for profile analysis")
            elif hasattr(completion, 'usage'):
                self.logger.info(f"Used {completion.usage.completion_tokens} completion tokens for profile analysis")
            
            response = completion.choices[0].message.content
            
            # Try to parse as JSON first
            try:
                response_data = json.loads(response)
                is_match = response_data.get("is_match", False)
                confidence = response_data.get("confidence", 50) / 100.0  # Convert from percentage to decimal
                reasoning = response_data.get("reasoning", "No detailed reasoning provided")
                
                # Add key evidence to reasoning
                key_evidence = response_data.get("key_evidence", [])
                if key_evidence:
                    reasoning += "\n\nKey Evidence:\n- " + "\n- ".join(key_evidence)
                
                # Add contradictory evidence to reasoning
                contradictory_evidence = response_data.get("contradictory_evidence", [])
                if contradictory_evidence:
                    reasoning += "\n\nContradictory Evidence:\n- " + "\n- ".join(contradictory_evidence)
                
                if self.logger:
                    self.logger.info(f"Profile analysis for {athlete_name}: match={is_match}, confidence={confidence:.2f}")
                
                return is_match, confidence, reasoning
            except json.JSONDecodeError:
                # If JSON parsing fails, use regex to extract information
                if self.logger:
                    self.logger.warning(f"Failed to parse JSON response for profile content analysis, using regex extraction")
                
                # Use the _parse_ai_response method to extract information
                match_result, confidence, reasoning = self._parse_ai_response(response, confidence_score)
                
                if self.logger:
                    self.logger.info(f"Profile analysis (regex) for {athlete_name}: match={match_result}, confidence={confidence:.2f}")
                
                return match_result, confidence, reasoning
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error analyzing profile content for {athlete_name}: {str(e)}")
            return False, 0.0, f"Error analyzing profile: {str(e)}"
    
    def _determine_ncaa_status(self, profile_data: Dict[str, Any], athlete_name: str) -> Tuple[bool, float, str]:
        """
        Stage 1: Determine if this profile belongs to an NCAA football player.
        
        Args:
            profile_data: Dict containing profile information
            athlete_name: Name of the athlete
            
        Returns:
            Tuple of (is_ncaa_player, confidence, reasoning)
        """
        if self.logger:
            self.logger.info(f"Stage 1: Determining NCAA status for profile related to {athlete_name}")
        
        # Pre-check for obvious NCAA indicators in URL
        url = ""
        for platform, value in profile_data.items():
            if platform in ['twitter', 'facebook', 'instagram', 'email', 'phone']:
                url = value.lower()
                break
        
        # Quick check for strong NCAA indicators
        is_likely_ncaa = False
        initial_confidence = 0.5  # Default starting confidence
        
        # Check for .edu domains (strong indicator)
        if '.edu' in url and any(term in url for term in ['athletics', 'sports', 'roster']):
            is_likely_ncaa = True
            initial_confidence = 0.8
        # Check for official NCAA domains
        elif 'ncaa.com' in url:
            is_likely_ncaa = True
            initial_confidence = 0.8
        # Check for team roster pages
        elif any(term in url for term in ['roster', 'player', 'bio', 'profile']) and any(term in url for term in ['football', 'athletics', 'sports']):
            is_likely_ncaa = True
            initial_confidence = 0.7
        # Check for non-sports sites (negative indicator)
        elif any(term in url for term in ['linkedin.com', 'indeed.com', 'career']):
            is_likely_ncaa = False
            initial_confidence = 0.2
        
        # Construct an enhanced prompt for NCAA status determination
        prompt = f"""
        Analyze this profile to determine if it belongs to an NCAA FOOTBALL PLAYER (not necessarily {athlete_name}, just any NCAA football player).
        
        PROFILE INFORMATION:
        """
        
        # Add profile information
        for platform, url in profile_data.items():
            if platform in ['twitter', 'facebook', 'instagram', 'email', 'phone']:
                prompt += f"- {platform.capitalize()}: {url}\n"
        
        # Add screenshot analysis if available
        if profile_data.get('screenshot_analysis'):
            prompt += f"\nSCREENSHOT ANALYSIS:\n{profile_data.get('screenshot_analysis')}\n"
        
        # Add reasoning from previous analysis if available
        if profile_data.get('reasoning'):
            prompt += f"\nPREVIOUS ANALYSIS:\n{profile_data.get('reasoning')}\n"
        
        prompt += """
        Focus ONLY on determining if this is an NCAA football player's profile by looking for:
        
        1. Clear references to college/NCAA football
        2. Mentions of football team, practice, games, or related activities
        3. References to a college/university athletic program
        4. Evidence of being a student-athlete
        5. Timeframe consistent with college eligibility
        6. Official team roster pages or athletic department websites
        7. Use of terms like "student-athlete," "NCAA," "college football"
        8. References to college classes, campus life alongside athletic activities
        
        IMPORTANT INDICATORS:
        - .edu domains with athletics/sports/roster in URL are strong positive indicators
        - Official NCAA or athletic department websites are strong positive indicators
        - Professional networking sites (LinkedIn, Indeed) are negative indicators
        - References to professional sports without college mentions are negative indicators
        
        DO NOT focus on whether this is the specific athlete named above - just determine if this is ANY NCAA football player.
        
        Provide your response as JSON with this structure:
        {
            "is_ncaa_player": true/false,
            "confidence": 0-100,
            "reasoning": "detailed explanation of your analysis",
            "evidence": ["specific evidence point 1", "specific evidence point 2", ...],
            "contradictions": ["contradictory evidence 1", "contradictory evidence 2", ...]
        }
        """
        
        # Get AI assessment
        system_instruction = "You are an expert at identifying NCAA football players from online profiles. Focus ONLY on determining if a profile belongs to any NCAA football player, not a specific individual."
        
        try:
            # Set up completion parameters
            completion_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Only add response_format if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["response_format"] = {"type": "json_object"}
                completion_params["temperature"] = 0.2
                
            completion = self.client.chat.completions.create(**completion_params)
            
            # Get the response content
            response_content = completion.choices[0].message.content
            
            # Parse the response
            try:
                result = json.loads(response_content)
                
                is_ncaa_player = result.get("is_ncaa_player", False)
                confidence = result.get("confidence", 50) / 100.0  # Convert from percentage
                reasoning = result.get("reasoning", "No detailed reasoning provided")
                
                # Add evidence if available
                evidence = result.get("evidence", [])
                if evidence:
                    reasoning += "\n\nEvidence:\n- " + "\n- ".join(evidence)
                
                # Add contradictory evidence if available
                contradictions = result.get("contradictions", [])
                if contradictions:
                    reasoning += "\n\nContradictions:\n- " + "\n- ".join(contradictions)
                
                return is_ncaa_player, confidence, reasoning
                
            except json.JSONDecodeError:
                # If JSON parsing fails, use regex to extract information
                self.logger.warning(f"JSON parsing failed for NCAA status determination, using fallback")
                
                # Simple fallback extraction
                is_ncaa_player = "is an NCAA football player" in response_content.lower()
                confidence = 0.5  # Default confidence when parsing fails
                
                return is_ncaa_player, confidence, f"Parsing failed, extracted content: {response_content[:200]}..."
                
        except Exception as e:
            self.logger.error(f"Error in NCAA status determination: {str(e)}")
            return False, 0.3, f"Error determining NCAA status: {str(e)}"
    
    def _verify_specific_player_match(self, 
                                    athlete_info: Dict[str, Any], 
                                    profile_data: Dict[str, Any],
                                    ncaa_confidence: float) -> Tuple[bool, float, str]:
        """
        Stage 2: Verify if this NCAA player profile matches our specific target athlete.
        
        Args:
            athlete_info: Dict containing athlete information
            profile_data: Dict containing profile information
            ncaa_confidence: Confidence from NCAA status determination
            
        Returns:
            Tuple of (is_match, confidence, reasoning)
        """
        athlete_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
        state = athlete_info.get('State', '')
        
        if self.logger:
            self.logger.info(f"Stage 2: Verifying specific player match for {athlete_name}")
        
        # Construct an enhanced prompt for specific player verification
        prompt = f"""
        Now that we've established this profile may belong to an NCAA football player, determine if it specifically matches:
        
        TARGET ATHLETE:
        - Name: {athlete_name}
        - State: {state if state else 'Unknown'}
        
        PROFILE INFORMATION:
        """
        
        # Add profile information
        for platform, url in profile_data.items():
            if platform in ['twitter', 'facebook', 'instagram', 'email', 'phone']:
                prompt += f"- {platform.capitalize()}: {url}\n"
        
        # Add screenshot analysis if available
        if profile_data.get('screenshot_analysis'):
            prompt += f"\nSCREENSHOT ANALYSIS:\n{profile_data.get('screenshot_analysis')}\n"
        
        prompt += f"""
        Focus on determining if this profile specifically belongs to {athlete_name} by:
        
        1. Analyzing name patterns in the profile URL/username
        2. Looking for explicit mentions of the athlete's name
        3. Checking for connections to the athlete's state ({state if state else 'Unknown'})
        4. Considering if there could be OTHER athletes or individuals with the same name
        5. Evaluating the likelihood this is the CORRECT {athlete_name}, not someone else with the same name
        
        IMPORTANT: Be especially careful to distinguish this specific athlete from others with similar names.
        
        Provide your response as JSON with this structure:
        {{
            "is_match": true/false,
            "confidence": 0-100,
            "reasoning": "detailed explanation of your analysis",
            "evidence": ["specific evidence point 1", "specific evidence point 2", ...],
            "contradictions": ["contradictory evidence 1", "contradictory evidence 2", ...],
            "possible_confusion": "explanation of potential confusion with others of same name (if applicable)"
        }}
        """
        
        # Get AI assessment
        system_instruction = "You are an expert at verifying if a profile belongs to a specific NCAA football player. Focus on distinguishing the target athlete from others with similar names."
        
        try:
            # Set up completion parameters
            completion_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Only add response_format if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["response_format"] = {"type": "json_object"}
                completion_params["temperature"] = 0.2
                
            completion = self.client.chat.completions.create(**completion_params)
            
            # Get the response content
            response_content = completion.choices[0].message.content
            
            # Parse the response
            try:
                result = json.loads(response_content)
                
                is_match = result.get("is_match", False)
                confidence = result.get("confidence", 50) / 100.0  # Convert from percentage
                
                # Weight the confidence by the NCAA confidence
                # If we're not confident this is an NCAA player, reduce match confidence
                adjusted_confidence = confidence * max(0.5, ncaa_confidence)
                
                reasoning = result.get("reasoning", "No detailed reasoning provided")
                
                # Add evidence if available
                evidence = result.get("evidence", [])
                if evidence:
                    reasoning += "\n\nEvidence:\n- " + "\n- ".join(evidence)
                
                # Add contradictory evidence if available
                contradictions = result.get("contradictions", [])
                if contradictions:
                    reasoning += "\n\nContradictions:\n- " + "\n- ".join(contradictions)
                
                # Add possible confusion with others
                possible_confusion = result.get("possible_confusion")
                if possible_confusion:
                    reasoning += f"\n\nPossible Confusion: {possible_confusion}"
                
                return is_match, adjusted_confidence, reasoning
                
            except json.JSONDecodeError:
                # If JSON parsing fails, use regex to extract information
                self.logger.warning(f"JSON parsing failed for specific player match, using fallback")
                
                # Simple fallback extraction
                is_match = f"is a match for {athlete_name}" in response_content.lower()
                confidence = 0.4  # Lower confidence when parsing fails
                
                return is_match, confidence, f"Parsing failed, extracted content: {response_content[:200]}..."
                
        except Exception as e:
            self.logger.error(f"Error in specific player match verification: {str(e)}")
            return False, 0.2, f"Error verifying specific player match: {str(e)}"
    
    def _check_disqualifying_evidence(self, 
                                    athlete_info: Dict[str, Any], 
                                    profile_data: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Stage 3: Check for disqualifying evidence that would rule out this profile.
        
        Args:
            athlete_info: Dict containing athlete information
            profile_data: Dict containing profile information
            
        Returns:
            Tuple of (has_disqualifiers, confidence, reasoning)
        """
        athlete_name = f"{athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}"
        
        if self.logger:
            self.logger.info(f"Stage 3: Checking for disqualifying evidence for {athlete_name}")
        
        # Construct a focused prompt for disqualifier detection
        prompt = f"""
        Analyze this profile for DISQUALIFYING EVIDENCE that would prove it CANNOT belong to NCAA football player {athlete_name}.
        
        PROFILE INFORMATION:
        """
        
        # Add profile information
        for platform, url in profile_data.items():
            if platform in ['twitter', 'facebook', 'instagram', 'email', 'phone']:
                prompt += f"- {platform.capitalize()}: {url}\n"
        
        # Add screenshot analysis if available
        if profile_data.get('screenshot_analysis'):
            prompt += f"\nSCREENSHOT ANALYSIS:\n{profile_data.get('screenshot_analysis')}\n"
        
        prompt += f"""
        Look SPECIFICALLY for evidence that would DISQUALIFY this profile, such as:
        
        1. Clear indication this person has a different profession (not a student or athlete)
        2. Evidence the person is in a different location/state with no connection to NCAA football
        3. Timeline inconsistencies (e.g., profile shows activity during a time when they would be too young/old for NCAA)
        4. Explicit self-identification as someone else
        5. Content that is completely unrelated to sports, college, or athletics
        
        IMPORTANT: Focus ONLY on finding STRONG DISQUALIFYING evidence, not just absence of confirming evidence.
        
        Provide your response as JSON with this structure:
        {{
            "has_disqualifiers": true/false,
            "confidence": 0-100,
            "reasoning": "detailed explanation of your analysis",
            "disqualifying_evidence": ["specific disqualifier 1", "specific disqualifier 2", ...]
        }}
        """
        
        # Get AI assessment
        system_instruction = "You are an expert at identifying evidence that would disqualify a profile from belonging to a specific NCAA football player. Focus only on strong disqualifying factors."
        
        try:
            # Set up completion parameters
            completion_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Only add response_format if not using o1-preview
            if not self.model.startswith("o1-"):
                completion_params["response_format"] = {"type": "json_object"}
                completion_params["temperature"] = 0.2
                
            completion = self.client.chat.completions.create(**completion_params)
            
            # Get the response content
            response_content = completion.choices[0].message.content
            
            # Parse the response
            try:
                result = json.loads(response_content)
                
                has_disqualifiers = result.get("has_disqualifiers", False)
                confidence = result.get("confidence", 50) / 100.0  # Convert from percentage
                reasoning = result.get("reasoning", "No detailed reasoning provided")
                
                # Add disqualifying evidence if available
                disqualifying_evidence = result.get("disqualifying_evidence", [])
                if disqualifying_evidence:
                    reasoning += "\n\nDisqualifying Evidence:\n- " + "\n- ".join(disqualifying_evidence)
                
                return has_disqualifiers, confidence, reasoning
                
            except json.JSONDecodeError:
                # If JSON parsing fails, use regex to extract information
                self.logger.warning(f"JSON parsing failed for disqualifier check, using fallback")
                
                # Simple fallback extraction
                has_disqualifiers = "disqualifying evidence" in response_content.lower()
                confidence = 0.4  # Lower confidence when parsing fails
                
                return has_disqualifiers, confidence, f"Parsing failed, extracted content: {response_content[:200]}..."
                
        except Exception as e:
            self.logger.error(f"Error in disqualifier check: {str(e)}")
            return False, 0.2, f"Error checking for disqualifiers: {str(e)}"
    
    def _build_verification_prompt(self, athlete_info: Dict, profile_data: Dict) -> str:
        """Legacy method: Build a detailed prompt for AI verification."""
        prompt = f"""
I need to verify if the following social media profile or contact information matches with the specified NCAA athlete.

ATHLETE INFORMATION:
- Name: {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}
- Sport: {athlete_info.get('Sport', 'Football')}
- State: {athlete_info.get('State', 'Unknown')}
- School/College: {athlete_info.get('School', 'Unknown')}
- Position: {athlete_info.get('Position', 'Unknown')}
- Year: {athlete_info.get('Year', 'Unknown')}

PROFILE INFORMATION:
"""
        # Add social media information if available
        if profile_data.get('twitter'):
            prompt += f"- Twitter: {profile_data.get('twitter')}\n"
        if profile_data.get('facebook'):
            prompt += f"- Facebook: {profile_data.get('facebook')}\n"
        if profile_data.get('instagram'):
            prompt += f"- Instagram: {profile_data.get('instagram')}\n"
        if profile_data.get('email'):
            prompt += f"- Email: {profile_data.get('email')}\n"
        if profile_data.get('phone'):
            prompt += f"- Phone: {profile_data.get('phone')}\n"
        
        # Add NCAA-specific context
        prompt += self._get_ncaa_context(athlete_info)
        
        prompt += """
Think step-by-step about this verification task:

1. Analyze the athlete's name, school, and sport
2. Check if the profile username or URL contains parts of the athlete's name
3. Consider common username patterns (first initial + last name, first name + last initial, etc.)
4. Consider if this is a team/school account rather than personal account
5. For email addresses, evaluate if they match school domains (.edu) or team domains
6. Look for evidence of NCAA athletic participation
7. Consider if this could be someone else with the same name who is NOT an NCAA athlete

Based on your analysis, please assess:
1. Is this profile likely to belong to the specified athlete? (yes/no)
2. On a scale from 0.0 to 1.0, what is your confidence score for this match?
3. What specific evidence supports or contradicts this match?
4. Are there any red flags suggesting this is NOT the correct athlete?
5. Suggest specific additional search terms that would help verify this profile further

Provide your response in this format:
MATCH: [yes/no]
CONFIDENCE: [0.0-1.0]
REASONING: [your detailed explanation]
RED_FLAGS: [list any concerning indicators]
SEARCH_SUGGESTIONS: [comma-separated list of specific search queries that would help verify further]
"""
        return prompt
    
    def _get_ncaa_context(self, athlete_info: Dict[str, Any]) -> str:
        """Get NCAA-specific context based on the athlete's sport and school."""
        sport = athlete_info.get('Sport', '').lower()
        
        sport_context = ""
        if sport == 'football':
            sport_context = """
NCAA Football athletes often:
- Have profiles on team roster pages with stats like yards, touchdowns, etc.
- May be listed on recruiting sites like 247Sports, Rivals, or ESPN
- Often use jersey numbers in usernames
- May reference bowl games, championships, or rivalry games
- Could have NFL draft profiles if upperclassmen
"""
        elif sport == 'basketball':
            sport_context = """
NCAA Basketball athletes often:
- Have profiles with stats like PPG (points per game), rebounds, assists
- May reference March Madness, Sweet Sixteen, Final Four
- Often have highlight reels on YouTube or social media
- May have NBA draft profiles if upperclassmen
"""
        elif sport in ['baseball', 'softball']:
            sport_context = """
NCAA Baseball/Softball athletes often:
- Have profiles with stats like batting average, ERA, home runs
- May reference College World Series
- Often have highlight reels or game footage
- May have MLB/professional draft profiles if upperclassmen
"""
        
        # Common NCAA context
        ncaa_context = f"""
ADDITIONAL NCAA CONTEXT:

{sport_context}

Common NCAA athlete profile patterns:
- Official team roster pages usually at athletics.[school].edu
- Athletes often mention team accomplishments, awards, championships
- May use school mascot or team nickname in profiles
- Often follow/are followed by teammates and coaches
- May have NIL (Name, Image, Likeness) sponsorship mentions
- Often have profile photos in uniform or at athletic facilities
"""
        
        return ncaa_context
    
    def _extract_twitter_username(self, url: str) -> Optional[str]:
        """Extract username from Twitter URL."""
        match = re.search(r'twitter\.com/([^/]+)', url)
        if match:
            username = match.group(1)
            # Skip common non-profile paths
            if username.lower() not in ['home', 'search', 'explore', 'notifications', 
                                      'messages', 'i', 'settings', 'compose']:
                return username
        return None
    
    def _extract_facebook_username(self, url: str) -> Optional[str]:
        """Extract username from Facebook URL."""
        # Handle profile.php?id= format
        if 'profile.php?id=' in url:
            match = re.search(r'profile\.php\?id=(\d+)', url)
            if match:
                return f"profile_{match.group(1)}"
        
        # Handle regular username format
        match = re.search(r'facebook\.com/([^/]+)', url)
        if match:
            username = match.group(1)
            # Skip common non-profile paths
            if username.lower() not in ['public', 'pages', 'groups', 'events', 
                                      'marketplace', 'watch', 'gaming']:
                return username
        return None
    
    def _extract_instagram_username(self, url: str) -> Optional[str]:
        """Extract username from Instagram URL."""
        match = re.search(r'instagram\.com/([^/]+)', url)
        if match:
            username = match.group(1)
            # Skip common non-profile paths
            if username.lower() not in ['explore', 'direct', 'stories', 'reels',
                                      'tv', 'shop', 'accounts']:
                return username
        return None
    
    def _parse_ai_response(self, ai_response: str, original_confidence: float) -> Tuple[bool, float, str]:
        """Parse the AI response to extract match decision, confidence, reasoning and search suggestions."""
        try:
            # Extract match decision
            match_result = False
            if "MATCH: yes" in ai_response.lower():
                match_result = True
            
            # Extract confidence score
            confidence = original_confidence  # Default to original
            confidence_match = re.search(r"CONFIDENCE:\s*(0\.\d+|1\.0)", ai_response)
            if confidence_match:
                ai_confidence = float(confidence_match.group(1))
                # Weight AI confidence more heavily
                confidence = (ai_confidence * 0.8) + (original_confidence * 0.2)
            
            # Extract reasoning
            reasoning = "No detailed reasoning provided"
            reasoning_match = re.search(r"REASONING:\s*(.*?)(?=$|MATCH:|CONFIDENCE:|SEARCH_SUGGESTIONS:)", ai_response, re.DOTALL)
            if reasoning_match:
                reasoning = reasoning_match.group(1).strip()
            
            # Extract search suggestions
            search_suggestions = []
            search_match = re.search(r"SEARCH_SUGGESTIONS:\s*(.*?)(?=$|MATCH:|CONFIDENCE:|REASONING:)", ai_response, re.DOTALL)
            if search_match and self.search_enabled:
                suggestions_text = search_match.group(1).strip()
                search_suggestions = [s.strip() for s in suggestions_text.split(',')]
                # Add search suggestions to reasoning
                if search_suggestions:
                    reasoning += "\n\nSUGGESTED SEARCHES: " + ", ".join(search_suggestions)
            
            return match_result, confidence, reasoning
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing AI response: {str(e)}")
            # Fall back to original confidence
            return original_confidence > 0.6, original_confidence, f"Failed to parse AI response: {ai_response[:100]}..."
