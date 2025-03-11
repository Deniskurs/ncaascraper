import pandas as pd
from tqdm import tqdm
import argparse
import os
import signal
import time
from datetime import datetime
from dotenv import load_dotenv
from utils.logger import setup_logger
from utils.driver import setup_chrome_driver
from utils.social_media_auth import SocialMediaAuth
from utils.url_validator import URLValidator
from services.enhanced_scraper_service import EnhancedScraperService
from components.profile_verifier import ProfileVerifier
from components.ai_verifier import AIVerifier
from components.active_learning import ActiveLearning

def check_file_structure():
    """Ensure required directories exist."""
    required_dirs = [
        'src/data/input',
        'src/data/output',
        'src/data/logs',
        'src/data/screenshots',
        'src/data/cache'
    ]
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def timeout_handler(signum, frame):
    """Raise an exception on timeout."""
    raise TimeoutError("Scraping took too long")

def main():
    print("Starting program...")
    check_file_structure()
    
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description='NCAA Athlete Social Media Scraper')
    parser.add_argument('--input', default='src/data/input/test_players.xlsx', help='Input Excel file path')
    parser.add_argument('--output', default='src/data/output/athletes_updated.xlsx', help='Output Excel file path')
    parser.add_argument('--openai-api-key', help='OpenAI API key for enhanced verification')
    parser.add_argument('--ai-verification', action='store_true', help='Enable AI verification for profile matching')
    parser.add_argument('--ai-model', default='gpt-4o', help='OpenAI model to use for reasoning (gpt-4o recommended)')
    parser.add_argument('--search-query-model', default='gpt-4o', help='OpenAI model to use for search query generation (gpt-4o recommended)')
    parser.add_argument('--vision-model', default='gpt-4o', help='OpenAI model to use for vision verification (gpt-4o recommended)')
    parser.add_argument('--vision-enabled', action='store_true', help='Enable vision verification for social media profiles')
    parser.add_argument('--active-learning', action='store_true', help='Enable active learning to improve results over time')
    parser.add_argument('--timeout', type=int, default=45, help='Timeout per athlete in seconds')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found at {args.input}")
        return
    print(f"Input file found at {args.input}")

    try:
        logger, success_logger, results_logger = setup_logger()
        logger.info("Starting scraper...")
    except Exception as e:
        print(f"Error setting up logger: {e}")
        return

    # Initialize AI verifier if enabled
    ai_verifier = None
    if args.ai_verification:
        api_key = args.openai_api_key or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("AI verification enabled but no API key provided")
            print("Error: AI verification enabled but no API key provided")
            return
        
        try:
            print(f"Initializing AI verification with {args.ai_model}...")
            ai_verifier = AIVerifier(
                api_key=api_key, 
                logger=logger, 
                model=args.ai_model,
                search_query_model=args.search_query_model
            )
            logger.info(f"AI verification initialized successfully with {args.ai_model}")
            print(f"AI verification initialized successfully with {args.ai_model}")
        except Exception as e:
            logger.error(f"Failed to initialize AI verification: {e}")
            print(f"Error initializing AI verification: {e}")
            return

    try:
        print("Attempting to read input file...")
        df = pd.read_excel(args.input)
        logger.info(f"Loaded {len(df)} athletes from {args.input}")
        print(f"Successfully loaded {len(df)} athletes")

        print("Setting up Chrome driver with session persistence...")
        driver = setup_chrome_driver(enable_cookies=True)
        
        # Authenticate with social media platforms
        print("Authenticating with social media platforms...")
        social_auth = SocialMediaAuth(driver, logger)
        auth_results = social_auth.authenticate_all()
        
        # Log authentication results
        for platform, result in auth_results.items():
            if result['success']:
                logger.info(f"Successfully authenticated with {platform}")
                print(f"✓ Successfully authenticated with {platform}")
            else:
                logger.warning(f"Failed to authenticate with {platform}: {result['message']}")
                print(f"✗ Failed to authenticate with {platform}: {result['message']}")
        
        # Initialize URL validator
        url_validator = URLValidator(logger)
        
        # Initialize active learning if enabled
        active_learning = None
        if args.active_learning:
            print("Initializing active learning component...")
            active_learning = ActiveLearning(logger=logger)
            logger.info("Active learning initialized")
            print("Active learning initialized")
            
            # Print active learning statistics
            stats = active_learning.get_statistics()
            logger.info(f"Active learning stats: {stats}")
            print(f"Active learning stats: Total verifications: {stats['total_verifications']}, Success rate: {stats.get('success_rate', 0):.2f}")
        
        # Initialize enhanced scraper with AI verifier and URL validator
        print("Initializing enhanced scraper with AI reasoning and URL validation...")
        
        # Check if vision is enabled
        vision_enabled = args.vision_enabled
        if vision_enabled:
            print("Vision verification is enabled")
        else:
            print("Vision verification is disabled")
            
        # Create the scraper with the authenticated driver and vision model
        scraper = EnhancedScraperService(
            driver, 
            logger, 
            success_logger, 
            ai_verifier=ai_verifier,
            vision_model=args.vision_model
        )
        
        # Set vision enabled flag
        scraper.vision_enabled = vision_enabled
        
        # Set active learning component
        scraper.active_learning = active_learning
        
        # Create profile verifier with AI integration if enabled
        profile_verifier = ProfileVerifier(
            max_workers=3,
            ai_verifier=ai_verifier,
            logger=logger
        )

        # Track processing times for adaptive timeout
        processing_times = []

        progress = tqdm(total=len(df), desc="Processing athletes")
        for index, row in df.iterrows():
            try:
                athlete_name = f"{row['First_Name']} {row['Last_Name']}"
                print(f"Processing athlete {index + 1}/{len(df)}: {athlete_name}")
                
                # Calculate adaptive timeout based on previous processing times
                if processing_times:
                    avg_time = sum(processing_times) / len(processing_times)
                    # Add 50% buffer to average time, but cap at 120 seconds
                    timeout = min(120, max(args.timeout, int(avg_time * 1.5)))
                else:
                    timeout = args.timeout
                
                # Set a timeout per athlete
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)
                logger.info(f"Setting timeout to {timeout} seconds for {athlete_name}")
                
                start_time = time.time()
                
                # Create athlete context for search and verification
                athlete_context = {
                    'First_Name': row['First_Name'],
                    'Last_Name': row['Last_Name'],
                    'Sport': row.get('Sport', ''),
                    'School': row.get('School', ''),
                    'Position': row.get('Position', ''),
                    'Year': row.get('Year', ''),
                    'username_patterns': [
                        row['First_Name'].lower(),
                        row['Last_Name'].lower(),
                        f"{row['First_Name'][0].lower()}{row['Last_Name'].lower()}",  # jsmith
                        f"{row['First_Name'].lower()}{row['Last_Name'][0].lower()}",  # johns
                        f"{row['First_Name'].lower()}.{row['Last_Name'].lower()}",    # john.smith
                        f"{row['First_Name'].lower()}_{row['Last_Name'].lower()}"     # john_smith
                    ],
                    'search_keywords': ['ncaa', 'athlete', 'college', 'football', 'basketball', 'sports']
                }
                
                # Get profile information from scraper with context
                profile_info = scraper.get_profile_info(
                    row['First_Name'], 
                    row['Last_Name'],
                    context=athlete_context
                )
                
                # Record processing time for adaptive timeout
                processing_time = time.time() - start_time
                processing_times.append(processing_time)
                logger.info(f"Processing time for {athlete_name}: {processing_time:.2f} seconds")
                
                # Reset alarm to avoid timeout during processing
                signal.alarm(0)
                
                # Process and store the results
                results = {}  # Store results for logging
                
                for field in ["email", "phone", "twitter", "facebook", "instagram"]:
                    value = profile_info.get(field)
                    if not value:
                        continue
                    
                    # Store the value in the DataFrame
                    df.at[index, field] = value
                    results[field] = value
                
                # Log detailed results in plain text
                if results:
                    result_str = f"{athlete_name} - "
                    fields = []
                    for field, value in results.items():
                        field_str = f"{field.capitalize()}: {value}"
                        fields.append(field_str)
                    result_str += ", ".join(fields)
                    results_logger.info(result_str)
                
                # Save progress periodically
                if index % 5 == 0:
                    df.to_excel(args.output, index=False)
                    logger.info(f"Progress saved at {index + 1}/{len(df)} athletes")
            except TimeoutError:
                logger.error(f"Timeout processing {athlete_name} after {timeout} seconds")
                print(f"Timeout for {athlete_name} after {timeout} seconds")
                continue
            except Exception as e:
                logger.error(f"Error processing {athlete_name}: {e}")
                print(f"Error processing athlete: {e}")
                continue
            finally:
                progress.update(1)

        df.to_excel(args.output, index=False)
        logger.info("Scraping completed successfully!")
        print("Scraping completed!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error occurred: {e}")
    finally:
        if 'progress' in locals():
            progress.close()
        if 'driver' in locals():
            driver.quit()
        print("Program finished.")

if __name__ == "__main__":
    main()
