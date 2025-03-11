# NCAA Athlete Social Media Scraper

A tool to scrape and verify social media profiles and contact information for NCAA athletes.

## Features

- Searches for athletes' social media profiles (Twitter, Facebook, Instagram)
- Finds contact information (email, phone)
- Verifies profile authenticity using multiple signals
- **NEW: Enhanced verification using OpenAI** to ensure correct athlete identification

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r src/requirements.txt
   ```

## Usage

Basic usage:
```
python src/main.py --input data/input/test_players.xlsx --output data/output/athletes_updated.xlsx
```

### Using AI Verification

To enable enhanced AI verification using OpenAI:
```
python src/main.py --ai-verification --openai-api-key YOUR_API_KEY
```

You can also set the `OPENAI_API_KEY` environment variable instead of passing it as an argument.

### Command Line Arguments

- `--input`: Path to input Excel file (default: data/input/test_players.xlsx)
- `--output`: Path to output Excel file (default: data/output/athletes_updated.xlsx)
- `--ai-verification`: Enable AI verification for profile matching
- `--openai-api-key`: Your OpenAI API key
- `--ai-model`: OpenAI model to use (default: gpt-4o-mini)

## Input Format

The input Excel file should contain at minimum:
- First_Name
- Last_Name

Optional additional columns:
- Sport
- School
- Position
- Year

## How AI Verification Works

The AI verification feature uses OpenAI's GPT-4o-mini model to:

1. Analyze athlete information (name, school, sport)
2. Compare it with found social media profiles and contact information
3. Make an expert assessment of whether the profiles belong to the correct athlete
4. Provide reasoning for its decision
5. Return a confidence score that blends with traditional verification methods
6. Generate additional search queries when standard searches fail to find profiles

### AI-Enhanced Search Process

The system uses AI in two key ways:

1. **Proactive Search**: If standard searches don't find social media profiles, the AI generates customized search queries based on:
   - Name variations and possible nicknames
   - School-specific terminology or abbreviations
   - Sport-specific terms athletes might use
   - Team-related identifiers

2. **Profile Verification**: For each profile found (either through standard or AI-guided search), the AI:
   - Analyzes whether the profile likely belongs to the target athlete
   - Provides a confidence score from 0.0 to 1.0
   - Explains its reasoning in detail
   - Suggests further verification steps if needed

The system applies AI verification most heavily to:
- Social media profiles (Twitter, Facebook, Instagram) 
- Email addresses without clear name matches
- Any profile with a borderline confidence score (0.4-0.8)

This approach helps ensure the scraper identifies the correct athletes, especially in cases of:
- Common names
- Athletes who use nicknames on social media
- School/team-specific usernames that don't contain the athlete's name
- Team accounts that might be confused with personal accounts