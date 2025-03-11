import os
import json
import time
import pickle
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

class ActiveLearning:
    """
    Active Learning component that improves search and verification over time.
    
    This class implements a feedback-based learning system that:
    1. Collects and stores verification results
    2. Improves search queries based on past successes
    3. Refines confidence thresholds for different types of athletes
    4. Implements feedback loops for continuous improvement
    5. Optimizes performance through caching and pattern recognition
    """
    
    def __init__(self, logger=None, cache_dir="src/data/cache"):
        """Initialize the active learning component."""
        self.logger = logger
        self.cache_dir = cache_dir
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # Initialize data structures
        self.verification_history = self._load_or_create("verification_history.pkl", {})
        self.query_effectiveness = self._load_or_create("query_effectiveness.pkl", {})
        self.confidence_thresholds = self._load_or_create("confidence_thresholds.pkl", {})
        self.pattern_cache = self._load_or_create("pattern_cache.pkl", {})
        
        # Track statistics
        self.stats = {
            "total_verifications": 0,
            "successful_verifications": 0,
            "cache_hits": 0,
            "pattern_matches": 0,
            "threshold_adjustments": 0
        }
    
    def record_verification(self, 
                           athlete_info: Dict[str, Any], 
                           platform: str, 
                           url: str, 
                           confidence: float, 
                           is_correct: Optional[bool] = None) -> None:
        """
        Record a verification result for learning.
        
        Args:
            athlete_info: Dictionary containing athlete information
            platform: Platform (twitter, facebook, instagram, email, phone)
            url: The URL or contact info that was verified
            confidence: The confidence score (0.0-1.0)
            is_correct: Whether this was manually verified as correct (None if unknown)
        """
        if self.logger:
            self.logger.info(f"Recording verification for {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}")
        
        # Create a key for this athlete
        athlete_key = f"{athlete_info.get('First_Name', '')}-{athlete_info.get('Last_Name', '')}"
        sport = athlete_info.get('Sport', 'unknown').lower()
        
        # Initialize athlete entry if not exists
        if athlete_key not in self.verification_history:
            self.verification_history[athlete_key] = {
                "info": athlete_info,
                "verifications": []
            }
        
        # Record this verification
        verification = {
            "platform": platform,
            "url": url,
            "confidence": confidence,
            "is_correct": is_correct,
            "timestamp": datetime.now().isoformat()
        }
        
        self.verification_history[athlete_key]["verifications"].append(verification)
        
        # Update statistics
        self.stats["total_verifications"] += 1
        if is_correct:
            self.stats["successful_verifications"] += 1
        
        # Update confidence thresholds for this sport
        if is_correct is not None:
            self._update_confidence_thresholds(sport, platform, confidence, is_correct)
        
        # Save updated data
        self._save_data("verification_history.pkl", self.verification_history)
    
    def record_query_effectiveness(self, 
                                 query: str, 
                                 athlete_info: Dict[str, Any], 
                                 platform: str, 
                                 found_matches: int, 
                                 highest_confidence: float) -> None:
        """
        Record the effectiveness of a search query.
        
        Args:
            query: The search query used
            athlete_info: Dictionary containing athlete information
            platform: Platform searched (twitter, facebook, instagram, email, phone, or "")
            found_matches: Number of matches found
            highest_confidence: Highest confidence score among matches
        """
        if self.logger:
            self.logger.debug(f"Recording query effectiveness: {query}")
        
        # Extract query patterns
        query_words = query.lower().split()
        sport = athlete_info.get('Sport', 'unknown').lower()
        
        # Record effectiveness for this query
        if query not in self.query_effectiveness:
            self.query_effectiveness[query] = {
                "total_uses": 0,
                "found_matches": 0,
                "total_confidence": 0.0,
                "by_platform": {},
                "by_sport": {}
            }
        
        # Update query stats
        self.query_effectiveness[query]["total_uses"] += 1
        self.query_effectiveness[query]["found_matches"] += found_matches
        self.query_effectiveness[query]["total_confidence"] += highest_confidence
        
        # Update platform-specific stats
        if platform not in self.query_effectiveness[query]["by_platform"]:
            self.query_effectiveness[query]["by_platform"][platform] = {
                "uses": 0,
                "matches": 0,
                "total_confidence": 0.0
            }
        
        self.query_effectiveness[query]["by_platform"][platform]["uses"] += 1
        self.query_effectiveness[query]["by_platform"][platform]["matches"] += found_matches
        self.query_effectiveness[query]["by_platform"][platform]["total_confidence"] += highest_confidence
        
        # Update sport-specific stats
        if sport not in self.query_effectiveness[query]["by_sport"]:
            self.query_effectiveness[query]["by_sport"][sport] = {
                "uses": 0,
                "matches": 0,
                "total_confidence": 0.0
            }
        
        self.query_effectiveness[query]["by_sport"][sport]["uses"] += 1
        self.query_effectiveness[query]["by_sport"][sport]["matches"] += found_matches
        self.query_effectiveness[query]["by_sport"][sport]["total_confidence"] += highest_confidence
        
        # Save updated data
        self._save_data("query_effectiveness.pkl", self.query_effectiveness)
    
    def suggest_queries(self, 
                      athlete_info: Dict[str, Any], 
                      platform: str = "", 
                      max_queries: int = 5) -> List[str]:
        """
        Suggest effective search queries based on past performance.
        
        Args:
            athlete_info: Dictionary containing athlete information
            platform: Platform to search (twitter, facebook, instagram, email, phone, or "")
            max_queries: Maximum number of queries to suggest
            
        Returns:
            List of suggested search queries
        """
        if self.logger:
            self.logger.info(f"Suggesting queries for {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}")
        
        # Get basic athlete info
        first_name = athlete_info.get('First_Name', '')
        last_name = athlete_info.get('Last_Name', '')
        sport = athlete_info.get('Sport', 'unknown').lower()
        school = athlete_info.get('School', '')
        position = athlete_info.get('Position', '')
        year = athlete_info.get('Year', '')
        state = athlete_info.get('State', '')
        mascot = athlete_info.get('Mascot', '')
        
        # Create pattern key for cache lookup with more specific context
        pattern_key = f"{sport}-{platform}"
        if position:
            pattern_key += f"-{position}"
        
        # Check pattern cache for similar athletes
        if pattern_key in self.pattern_cache:
            self.stats["pattern_matches"] += 1
            pattern_queries = self.pattern_cache[pattern_key]
            
            # Personalize the cached queries for this athlete with more context
            personalized_queries = []
            for query_template in pattern_queries:
                personalized = query_template.replace("{first_name}", first_name)
                personalized = personalized.replace("{last_name}", last_name)
                personalized = personalized.replace("{school}", school if school else "")
                personalized = personalized.replace("{position}", position if position else "")
                personalized = personalized.replace("{year}", year if year else "")
                personalized = personalized.replace("{state}", state if state else "")
                personalized = personalized.replace("{mascot}", mascot if mascot else "")
                personalized = personalized.replace("{sport}", sport)
                
                # Clean up any double spaces from empty replacements
                personalized = " ".join(personalized.split())
                personalized_queries.append(personalized)
            
            if personalized_queries:
                return personalized_queries[:max_queries]
        
        # Find most effective queries for this sport and platform
        effective_queries = []
        
        for query, stats in self.query_effectiveness.items():
            # Skip queries with no matches
            if stats["found_matches"] == 0:
                continue
            
            # Calculate effectiveness score with more sophisticated metrics
            platform_score = 0
            if platform in stats["by_platform"]:
                platform_stats = stats["by_platform"][platform]
                if platform_stats["uses"] > 0:
                    # Consider both match rate and confidence
                    match_rate = platform_stats["matches"] / platform_stats["uses"]
                    avg_confidence = platform_stats["total_confidence"] / platform_stats["uses"]
                    # Weight match rate more heavily than confidence
                    platform_score = (match_rate * 0.7) + (avg_confidence * 0.3)
            
            sport_score = 0
            if sport in stats["by_sport"]:
                sport_stats = stats["by_sport"][sport]
                if sport_stats["uses"] > 0:
                    # Consider both match rate and confidence
                    match_rate = sport_stats["matches"] / sport_stats["uses"]
                    avg_confidence = sport_stats["total_confidence"] / sport_stats["uses"]
                    # Weight match rate more heavily than confidence
                    sport_score = (match_rate * 0.7) + (avg_confidence * 0.3)
            
            # Combined score with sport given higher weight
            effectiveness = (sport_score * 0.7) + (platform_score * 0.3)
            
            # Apply usage bonus for frequently successful queries
            if stats["total_uses"] > 5 and (stats["found_matches"] / stats["total_uses"]) > 0.5:
                effectiveness *= 1.2  # 20% bonus for proven queries
            
            if effectiveness > 0:
                # Create a template from this query with more context variables
                template = query
                template = template.replace(first_name, "{first_name}")
                template = template.replace(last_name, "{last_name}")
                if school:
                    template = template.replace(school, "{school}")
                if position:
                    template = template.replace(position, "{position}")
                if year:
                    template = template.replace(year, "{year}")
                if state:
                    template = template.replace(state, "{state}")
                if mascot:
                    template = template.replace(mascot, "{mascot}")
                
                # Create personalized query
                personalized = template.replace("{first_name}", first_name)
                personalized = personalized.replace("{last_name}", last_name)
                personalized = personalized.replace("{school}", school if school else "")
                personalized = personalized.replace("{position}", position if position else "")
                personalized = personalized.replace("{year}", year if year else "")
                personalized = personalized.replace("{state}", state if state else "")
                personalized = personalized.replace("{mascot}", mascot if mascot else "")
                personalized = personalized.replace("{sport}", sport)
                
                # Clean up any double spaces from empty replacements
                personalized = " ".join(personalized.split())
                
                effective_queries.append((personalized, effectiveness, template))
        
        # Sort by effectiveness
        effective_queries.sort(key=lambda x: x[1], reverse=True)
        
        # Extract just the queries
        result_queries = [q[0] for q in effective_queries[:max_queries]]
        
        # If we found effective queries, cache the templates for future use
        if effective_queries:
            templates = [q[2] for q in effective_queries[:max_queries]]
            self.pattern_cache[pattern_key] = templates
            self._save_data("pattern_cache.pkl", self.pattern_cache)
        
        # If we don't have enough queries, add NCAA-specific defaults
        if len(result_queries) < max_queries:
            defaults = []
            
            # NCAA-specific queries with official sources
            if school:
                defaults.extend([
                    f"{first_name} {last_name} site:.edu athletics roster football",
                    f"{first_name} {last_name} {school} athletics football roster",
                ])
                
                # Try to form a domain like "athletics.harvard.edu"
                school_words = school.lower().split()
                if len(school_words) > 1:
                    domain = f"athletics.{school_words[-1]}.edu"
                    defaults.append(f"{first_name} {last_name} site:{domain}")
            
            # Position-specific query
            if position:
                defaults.append(f"{first_name} {last_name} ncaa football {position}")
            
            # State-specific query
            if state:
                defaults.append(f"{first_name} {last_name} {state} college football player")
            
            # General NCAA queries
            defaults.extend([
                f"{first_name} {last_name} ncaa.com football profile",
                f"{first_name} {last_name} {sport} athlete",
                f"{first_name} {last_name} {school} {sport}",
                f"{first_name} {last_name} ncaa {sport}",
                f"{first_name} {last_name} college {sport}",
                f"{first_name} {last_name} {school} athletics"
            ])
            
            # Add defaults that aren't already in our results
            for default in defaults:
                if default not in result_queries:
                    result_queries.append(default)
                    if len(result_queries) >= max_queries:
                        break
        
        return result_queries[:max_queries]
    
    def get_confidence_threshold(self, 
                               athlete_info: Dict[str, Any], 
                               platform: str) -> float:
        """
        Get the adaptive confidence threshold for a specific athlete and platform.
        
        Args:
            athlete_info: Dictionary containing athlete information
            platform: Platform (twitter, facebook, instagram, email, phone)
            
        Returns:
            Confidence threshold (0.0-1.0)
        """
        sport = athlete_info.get('Sport', 'unknown').lower()
        
        # Default thresholds
        default_thresholds = {
            "twitter": 0.6,
            "facebook": 0.65,
            "instagram": 0.6,
            "email": 0.7,
            "phone": 0.75
        }
        
        # Get sport-specific threshold if available
        if sport in self.confidence_thresholds and platform in self.confidence_thresholds[sport]:
            self.stats["cache_hits"] += 1
            return self.confidence_thresholds[sport][platform]
        
        # Fall back to default
        return default_thresholds.get(platform, 0.7)
    
    def provide_feedback(self, 
                       athlete_info: Dict[str, Any], 
                       platform: str, 
                       url: str, 
                       is_correct: bool) -> None:
        """
        Provide manual feedback about a verification result.
        
        Args:
            athlete_info: Dictionary containing athlete information
            platform: Platform (twitter, facebook, instagram, email, phone)
            url: The URL or contact info
            is_correct: Whether this was correctly identified
        """
        if self.logger:
            self.logger.info(f"Receiving feedback for {athlete_info.get('First_Name', '')} {athlete_info.get('Last_Name', '')}")
        
        # Find the verification in history
        athlete_key = f"{athlete_info.get('First_Name', '')}-{athlete_info.get('Last_Name', '')}"
        
        if athlete_key in self.verification_history:
            athlete_data = self.verification_history[athlete_key]
            
            # Find the specific verification
            for verification in athlete_data["verifications"]:
                if verification["platform"] == platform and verification["url"] == url:
                    # Update the verification with feedback
                    verification["is_correct"] = is_correct
                    verification["feedback_timestamp"] = datetime.now().isoformat()
                    
                    # Record the confidence score for threshold adjustment
                    sport = athlete_info.get('Sport', 'unknown').lower()
                    self._update_confidence_thresholds(sport, platform, verification["confidence"], is_correct)
                    
                    # Save updated data
                    self._save_data("verification_history.pkl", self.verification_history)
                    return
        
        # If we didn't find the verification, add it
        self.record_verification(athlete_info, platform, url, 0.5, is_correct)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the active learning system."""
        stats = self.stats.copy()
        
        # Add additional statistics
        stats["verification_history_size"] = len(self.verification_history)
        stats["query_effectiveness_size"] = len(self.query_effectiveness)
        stats["pattern_cache_size"] = len(self.pattern_cache)
        
        # Calculate success rate
        if stats["total_verifications"] > 0:
            stats["success_rate"] = stats["successful_verifications"] / stats["total_verifications"]
        else:
            stats["success_rate"] = 0.0
        
        return stats
    
    def _update_confidence_thresholds(self, sport: str, platform: str, confidence: float, is_correct: bool) -> None:
        """Update confidence thresholds based on feedback."""
        # Initialize sport entry if not exists
        if sport not in self.confidence_thresholds:
            self.confidence_thresholds[sport] = {}
        
        # Initialize platform entry if not exists
        if platform not in self.confidence_thresholds[sport]:
            self.confidence_thresholds[sport][platform] = 0.7  # Default threshold
        
        current_threshold = self.confidence_thresholds[sport][platform]
        
        # Adjust threshold based on feedback
        if is_correct and confidence < current_threshold:
            # Lower threshold slightly if we're missing correct matches
            new_threshold = max(0.5, current_threshold - 0.05)
            self.confidence_thresholds[sport][platform] = new_threshold
            self.stats["threshold_adjustments"] += 1
            
            if self.logger:
                self.logger.info(f"Lowered threshold for {sport}/{platform} to {new_threshold:.2f}")
                
        elif not is_correct and confidence >= current_threshold:
            # Raise threshold if we're accepting incorrect matches
            new_threshold = min(0.9, current_threshold + 0.05)
            self.confidence_thresholds[sport][platform] = new_threshold
            self.stats["threshold_adjustments"] += 1
            
            if self.logger:
                self.logger.info(f"Raised threshold for {sport}/{platform} to {new_threshold:.2f}")
        
        # Save updated thresholds
        self._save_data("confidence_thresholds.pkl", self.confidence_thresholds)
    
    def _load_or_create(self, filename: str, default_value: Any) -> Any:
        """Load data from a file or create it if it doesn't exist."""
        filepath = os.path.join(self.cache_dir, filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error loading {filename}: {str(e)}")
                return default_value
        else:
            return default_value
    
    def _save_data(self, filename: str, data: Any) -> None:
        """Save data to a file."""
        filepath = os.path.join(self.cache_dir, filename)
        
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error saving {filename}: {str(e)}")
