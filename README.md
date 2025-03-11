# NCAA Athlete Social Media Scraper

A sophisticated tool for identifying and verifying social media profiles and contact information for NCAA athletes with high accuracy.

## Features

- Searches for athletes' social media profiles (Twitter, Facebook, Instagram)
- Finds contact information (email, phone)
- Verifies profile authenticity using multiple verification signals
- Enhanced AI-powered verification to ensure correct athlete identification
- Active learning system that improves accuracy over time
- Optional vision-based verification for social media profiles
- **Social media authentication** to access restricted content
- **Enhanced URL validation** to filter out generic pages and invalid PHP endpoints

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd ncaascraper
   ```

2. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r src/requirements.txt
   ```

4. Set up environment variables:

   Create a `.env` file in the project root with your OpenAI API key:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

### Basic Usage

Run the scraper with default settings:

```bash
python src/main.py
```

This will:

- Read athlete data from `src/data/input/test_players.xlsx`
- Output results to `src/data/output/athletes_updated.xlsx`
- Use basic verification methods (no AI)

### Command Line Arguments

| Argument               | Description                                          | Default                                 |
| ---------------------- | ---------------------------------------------------- | --------------------------------------- |
| `--input`              | Path to input Excel file                             | `src/data/input/test_players.xlsx`      |
| `--output`             | Path to output Excel file                            | `src/data/output/athletes_updated.xlsx` |
| `--openai-api-key`     | OpenAI API key (can also be set in `.env` file)      | None                                    |
| `--ai-verification`    | Enable AI verification for profile matching          | False                                   |
| `--ai-model`           | OpenAI model to use for reasoning                    | `gpt-4o`                                |
| `--search-query-model` | OpenAI model to use for search query generation      | `gpt-4o`                                |
| `--vision-model`       | OpenAI model to use for vision verification          | `gpt-4o`                                |
| `--vision-enabled`     | Enable vision verification for social media profiles | False                                   |
| `--active-learning`    | Enable active learning to improve results over time  | False                                   |
| `--timeout`            | Timeout per athlete in seconds                       | 45                                      |

### Example Run Configurations

#### Basic Run (No AI)

```bash
python src/main.py --input data/input/my_athletes.xlsx --output data/output/results.xlsx
```

#### AI-Enhanced Verification

```bash
python src/main.py --ai-verification
```

#### Full AI Enhancement with Active Learning

```bash
python src/main.py --ai-verification --active-learning --vision-enabled --timeout 60
```

#### Custom Models and Extended Timeout

```bash
python src/main.py --ai-verification --ai-model gpt-4o --search-query-model gpt-4o --timeout 90
```

#### Using Vision Verification with Custom Model

```bash
python src/main.py --ai-verification --vision-enabled --vision-model gpt-4o --timeout 60
```

#### Processing a Large Dataset

```bash
python src/main.py --input data/input/large_dataset.xlsx --output data/output/large_results.xlsx --timeout 120
```

> **Note**: The `--timeout` parameter always requires a numeric value (in seconds). For example, `--timeout 60` sets a 60-second timeout per athlete.

## Input Format

The input Excel file should contain at minimum:

- `First_Name`
- `Last_Name`

Optional additional columns that improve accuracy:

- `Sport`
- `School`
- `Position`
- `Year`
- `State`

## How It Works

### Social Media Authentication

The social media authentication feature:

1. Automatically logs into Twitter, Facebook, and Instagram before scraping
2. Uses credentials stored in the `.env` file
3. Maintains session persistence throughout the scraping process
4. Enables access to restricted content that requires authentication
5. Captures screenshots for debugging authentication issues

To set up social media authentication, add the following to your `.env` file:

```
# Social Media Credentials
FACEBOOK_EMAIL=your_facebook_email
FACEBOOK_PASSWORD=your_facebook_password
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
TWITTER_EMAIL=your_twitter_email
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password
```

### Enhanced URL Validation

The URL validation system:

1. Filters out generic social media pages that aren't athlete profiles
2. Validates PHP endpoints to ensure they're actual profile pages
3. Uses platform-specific patterns to identify genuine profiles
4. Analyzes URL content to detect athlete-related indicators
5. Improves accuracy by reducing false positives from generic pages

### AI-Enhanced Verification

The AI verification feature uses OpenAI's models to:

1. Generate optimized search queries based on athlete information
2. Analyze search results to identify potential profiles
3. Verify profiles through multi-stage verification:
   - NCAA status determination (Is this an NCAA player at all?)
   - Specific athlete matching (Is this the correct NCAA player?)
   - Disqualifying evidence check (Is there anything that rules this out?)
4. Provide detailed reasoning and confidence scores

### Active Learning

The active learning system:

1. Records verification results and search query effectiveness
2. Adapts confidence thresholds based on feedback
3. Improves search queries based on past successes
4. Implements pattern recognition for similar athletes
5. Gets more accurate over time as it processes more athletes

### Vision Verification

When enabled, the vision verification feature:

1. Captures screenshots of social media profiles
2. Uses AI vision models (gpt-4o) to analyze profile images
3. Looks for visual evidence connecting the profile to the athlete
4. Integrates visual analysis with text-based verification

> **Note**: The vision verification feature now uses the gpt-4o model, which has built-in vision capabilities, replacing the deprecated gpt-4-vision-preview model.

## Best Practices

- Use the `--ai-verification` flag for maximum accuracy
- Enable `--active-learning` for long-term improvements
- Set appropriate `--timeout` values based on your dataset size
- Store your OpenAI API key in the `.env` file rather than passing it as a command-line argument
- For critical applications, enable `--vision-enabled` for additional verification
- **Set up social media authentication** to access restricted profiles and improve results
- Use a dedicated social media account for scraping to avoid account restrictions

## Troubleshooting

- If you encounter timeout errors, increase the `--timeout` value
- Ensure your input Excel file has the required columns
- Check that your OpenAI API key is valid and has sufficient quota
- For vision verification issues, ensure Chrome is properly installed
- If social media authentication fails, check your credentials in the `.env` file
- For PHP endpoint issues, verify the URL validation is working correctly
- If you see "session expired" errors, try clearing the Chrome data directory and restarting
