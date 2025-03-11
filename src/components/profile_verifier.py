from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import re
from typing import List, Dict, Optional

@dataclass
class ProfileScore:
    url: str
    confidence: float
    matching_signals: List[str]
    ai_verified: bool = False
    ai_reasoning: Optional[str] = None

class ProfileVerifier:
    def __init__(self, max_workers=3, ai_verifier=None, logger=None):
        self.max_workers = max_workers
        self.verification_cache = {}
        self.ai_verifier = ai_verifier
        self.logger = logger
        self.ai_verification_enabled = ai_verifier is not None
        
    def verify_profiles_batch(self, profiles: List[dict], athlete_context: dict) -> Dict[str, ProfileScore]:
        """Verify multiple profiles concurrently."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for profile in profiles:
                if profile['url'] in self.verification_cache:
                    continue
                futures.append(
                    executor.submit(self._score_profile, profile, athlete_context)
                )
            
            results = {}
            for future in futures:
                score = future.result()
                # Apply AI verification for borderline cases if enabled
                if self.ai_verification_enabled and 0.4 <= score.confidence <= 0.8:
                    self._apply_ai_verification(score, profile, athlete_context)
                
                if score.confidence > 0.6:  # Minimum confidence threshold
                    results[score.url] = score
                    self.verification_cache[score.url] = score
            return results
    
    def _apply_ai_verification(self, score: ProfileScore, profile: dict, athlete_context: dict) -> None:
        """Apply AI verification to refine the confidence score."""
        try:
            if self.logger:
                self.logger.info(f"Applying AI verification for {profile.get('url', 'unknown profile')}")
            
            is_match, adjusted_confidence, reasoning = self.ai_verifier.verify_profile_match(
                athlete_info=athlete_context,
                profile_data=profile,
                confidence_score=score.confidence
            )
            
            # Update the score with AI verification results
            score.confidence = adjusted_confidence
            score.ai_verified = True
            score.ai_reasoning = reasoning
            
            # Add AI verification as a signal
            if is_match:
                score.matching_signals.append('ai_verified_match')
            else:
                score.matching_signals.append('ai_verified_nonmatch')
                
            if self.logger:
                self.logger.info(f"AI verification completed: confidence adjusted to {adjusted_confidence:.2f}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"AI verification failed: {str(e)}")
            # AI verification failed, but we continue with the original score

    def _score_profile(self, profile: dict, context: dict) -> ProfileScore:
        """Score a profile based on multiple signals with enhanced NCAA-specific patterns."""
        signals = []
        confidence = 0.0
        url_lower = profile.get('url', '').lower()
        
        # Initialize base confidence based on source credibility
        source_credibility = profile.get('source_credibility', 'unknown')
        if source_credibility == 'high':
            confidence += 0.3
            signals.append('high_credibility_source')
        elif source_credibility == 'medium':
            confidence += 0.15
            signals.append('medium_credibility_source')
        
        # Check for official NCAA or educational sources
        if '.edu' in url_lower and any(term in url_lower for term in ['athletics', 'sports', 'roster']):
            confidence += 0.3
            signals.append('official_edu_athletics_source')
        elif 'ncaa.com' in url_lower:
            confidence += 0.3
            signals.append('official_ncaa_source')
        elif any(term in url_lower for term in ['roster', 'player', 'bio', 'profile']):
            confidence += 0.15
            signals.append('player_profile_page')
            
        # Penalize non-sports sites
        if any(term in url_lower for term in ['linkedin.com', 'indeed.com', 'career']):
            confidence -= 0.3
            signals.append('professional_profile_penalty')
        
        # Check username patterns in URL with more precise matching
        name_parts = [
            context.get('First_Name', '').lower(),
            context.get('Last_Name', '').lower()
        ]
        
        # More precise username pattern matching
        if any(pattern in url_lower for pattern in context.get('username_patterns', [])):
            # Check if it's a direct match (not just substring)
            for pattern in context.get('username_patterns', []):
                # Extract username from URL for social media profiles
                username_match = re.search(r'(?:twitter\.com|facebook\.com|instagram\.com)/([^/?]+)', url_lower)
                if username_match:
                    username = username_match.group(1)
                    # Exact or very close match
                    if username == pattern or username.startswith(pattern):
                        confidence += 0.4
                        signals.append('exact_username_match')
                        break
                    # Partial match
                    elif pattern in username:
                        confidence += 0.2
                        signals.append('partial_username_match')
                        break
                # For non-social media URLs
                elif pattern in url_lower:
                    confidence += 0.2
                    signals.append('url_contains_username_pattern')
        
        # Check NCAA/athlete keywords in URL with weighted scoring
        ncaa_keywords = context.get('search_keywords', ['ncaa', 'athlete', 'college', 'football'])
        for kw in ncaa_keywords:
            if kw in url_lower:
                # School name is a stronger signal
                if kw == context.get('School', '').lower():
                    confidence += 0.25
                    signals.append('school_name_match')
                # Position is a good signal
                elif kw == context.get('Position', '').lower():
                    confidence += 0.2
                    signals.append('position_match')
                # Team mascot is a good signal
                elif kw == context.get('Mascot', '').lower():
                    confidence += 0.2
                    signals.append('mascot_match')
                # General NCAA keywords
                elif kw in ['ncaa', 'athlete', 'football', 'college']:
                    confidence += 0.1
                    signals.append(f'keyword_match_{kw}')
        
        # Email-specific scoring with enhanced validation
        if 'email' in profile and profile['email']:
            email_lower = profile['email'].lower()
            
            # Educational email is a strong signal
            if email_lower.endswith('.edu'):
                confidence += 0.3
                signals.append('edu_email_domain')
                
                # School name in email is even stronger
                school = context.get('School', '')
                if school and school.lower() in email_lower:
                    confidence += 0.2
                    signals.append('school_in_email')
            
            # Name match in email
            if any(part in email_lower for part in name_parts):
                confidence += 0.2
                signals.append('name_in_email')
                
            # More precise pattern matching for email
            for pattern in context.get('username_patterns', []):
                email_username = email_lower.split('@')[0]
                if pattern == email_username:
                    confidence += 0.3
                    signals.append('exact_email_username_match')
                    break
                elif pattern in email_username:
                    confidence += 0.15
                    signals.append('partial_email_username_match')
        
        # Bio/description analysis with enhanced context matching
        if 'bio' in profile and profile['bio']:
            bio_lower = profile['bio'].lower()
            
            # Check for school name in bio
            if context.get('School') and context.get('School').lower() in bio_lower:
                confidence += 0.25
                signals.append('school_in_bio')
                
            # Check for position in bio
            if context.get('Position') and context.get('Position').lower() in bio_lower:
                confidence += 0.2
                signals.append('position_in_bio')
                
            # Check for year (freshman, sophomore, etc.)
            if context.get('Year') and context.get('Year').lower() in bio_lower:
                confidence += 0.15
                signals.append('year_in_bio')
                
            # Check for NCAA/football references
            if any(term in bio_lower for term in ['ncaa', 'college football', 'athlete']):
                confidence += 0.2
                signals.append('ncaa_reference_in_bio')
        
        # Consider any AI reasoning provided in the profile
        if 'reasoning' in profile and profile['reasoning']:
            reasoning_lower = profile['reasoning'].lower()
            
            # Positive signals in reasoning
            if any(term in reasoning_lower for term in ['official', 'verified', 'confirmed']):
                confidence += 0.1
                signals.append('positive_ai_reasoning')
                
            # Negative signals in reasoning
            if any(term in reasoning_lower for term in ['unrelated', 'different person', 'not the athlete']):
                confidence -= 0.2
                signals.append('negative_ai_reasoning')

        return ProfileScore(
            url=profile['url'],
            confidence=min(confidence, 1.0),
            matching_signals=signals
        )
