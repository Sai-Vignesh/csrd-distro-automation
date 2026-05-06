# Standard Operating Procedure (SOP): DistroAutomation Tool

**Purpose:** This procedure explains how to use the DistroAutomation tool to fetch attendees from our Eventbrite waitlist and add them to the CSRD Newsletter distribution list.

**Where to find it:**
The tool is currently located on the local machine at: `Desktop\DistroFiller\DistroAutomation`.
*(Note: Ensure you have downloaded the latest version from the Center's Drive or GitHub if running on a new computer).*

---

## Method 1: Using the Web Interface (Recommended)

This method allows you to use a friendly graphical interface to upload attendee lists and track progress.

**Step 1: Start the Web Interface**
1. Open a Command Prompt or PowerShell window.
2. Navigate to the tool's folder:
   ```cmd
   cd Desktop\DistroFiller\DistroAutomation
   ```
3. Run the following command to start the application:
   ```cmd
   uv run python -m src.web.app
   ```
4. A browser window will automatically open to `http://localhost:5000`.

**Step 2: Upload and Process**
1. On the web page, click **"Choose File"** and select your CSV file containing the attendees.
   *(Note: The CSV must contain `first_name`, `last_name`, and `email` columns).*
2. Select the number of parallel workers (10 is recommended for fast processing).
3. Click **"Start Processing"**.
4. The screen will show you real-time updates as each person is successfully added to the newsletter!
5. When finished, you can close the command prompt window to stop the server.

---

## Method 2: One-Click Automation (Advanced)

If you know the **Eventbrite Event ID**, you can skip the CSV upload step entirely. The program will automatically log in to Eventbrite, find everyone who answered "Yes" to the waitlist/newsletter question, and add them.

**Step 1: Find the Event ID**
1. Log into Eventbrite and go to your Event Dashboard.
2. Look at the URL in your browser. It will look something like this: `https://www.eventbrite.com/myevent?eid=123456789012`
3. The number (`123456789012`) is your Event ID.

**Step 2: Run the Command**
1. Open Command Prompt or PowerShell.
2. Navigate to the tool's folder:
   ```cmd
   cd Desktop\DistroFiller\DistroAutomation
   ```
3. Run the following command, replacing `EVENT_ID` with your actual number:
   ```cmd
   uv run python -m src.cli.run_cli 123456789012
   ```
4. The tool will output the number of people it found and immediately start adding them to the distribution list.

---

## Troubleshooting

- **Error: "Unsupported file format"** 
  Make sure your file is a `.csv` or `.xlsx` file, and that it has columns named exactly `first_name`, `last_name`, and `email`.
- **The browser doesn't open when starting the Web App**
  Manually open Chrome or Edge and go to `http://localhost:5000`.
- **Eventbrite API errors**
  Ensure the Event ID is correct and that the API key hasn't expired. Contact IT support if the API key needs refreshing.
