# DistroAutomation

This repository automates the workflow of extracting waitlisted attendees from Eventbrite and automatically adding them to the CSRD newsletter distribution list.

It combines both the Eventbrite API data extraction and Playwright browser automation into a single, unified codebase.

## Prerequisites

- **Python 3.12+**
- `uv` package manager (recommended for fast virtual environments)

## Setup

1. **Install Dependencies:**
   ```bash
   uv sync
   ```

2. **Install Playwright Browsers:**
   Playwright needs a Chromium browser to perform the automated form filling.
   ```bash
   uv run playwright install chromium
   ```

## Usage

This project supports multiple modes of operation depending on your technical comfort level.

### 1. Web Application (Recommended for Most Users)

A user-friendly web interface that allows you to upload an exported CSV file and watch the progress of form submission.

```bash
# Start the web app (opens automatically in your browser)
uv run python -m src.web.app
```

### 2. Command Line Interface (CLI) - End-to-End Automation

If you have an Eventbrite Event ID, you can automatically fetch waitlisted attendees and submit them to the distribution list in one command.

```bash
# Run end-to-end processing with default settings
uv run python -m src.cli.run_cli <EVENT_ID>

# Customize the run (show browser visibility, use 5 parallel workers)
uv run python -m src.cli.run_cli <EVENT_ID> --headed --workers 5
```

### 3. Extract Unique Eventbrite Questions

If you need to analyze the custom questions attendees answered for a specific event:

```bash
uv run python -m src.eventbrite.question_utils <EVENT_ID>
```
This will generate a `unique_questions.json` file.

## Project Structure

- `src/eventbrite/` - Logic for fetching and filtering attendees via Eventbrite API.
- `src/automation/` - Playwright automation logic for filling out the exact target distribution form.
- `src/web/` - Flask application providing a graphical user interface.
- `src/cli/` - Command-line tools for executing end-to-end workflows.
- `data/` - Sample and testing data.

## Configuration

If the Eventbrite API Key needs to be updated, you can find it defined in `src/eventbrite/fetcher.py`. (Note: In a production environment, this should ideally be moved to a `.env` file.)
