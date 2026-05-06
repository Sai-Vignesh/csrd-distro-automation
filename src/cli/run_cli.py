import argparse
import asyncio
import sys
import os

from src.eventbrite.fetcher import get_attendees, filter_waitlist_attendees, export_to_csv
from src.automation.form_submitter import process_file

def main():
    parser = argparse.ArgumentParser(description="Fetch Eventbrite attendees and add them to the newsletter.")
    parser.add_argument("event_id", type=str, help="The ID of the Eventbrite event")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers (default: 10)")
    parser.add_argument("--keep-csv", action="store_true", help="Keep the temporary CSV file after processing")
    
    args = parser.parse_args()

    # Step 1: Fetch and filter attendees
    print(f"--- Fetching attendees from Eventbrite (Event ID: {args.event_id}) ---")
    attendees = get_attendees(args.event_id)
    if attendees is None:
        print("Failed to fetch attendees from Eventbrite. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Total attendees fetched: {len(attendees)}")
    
    waitlist_attendees = filter_waitlist_attendees(attendees)
    print(f"Attendees who answered 'yes' to the waitlist question: {len(waitlist_attendees)}")
    
    if len(waitlist_attendees) == 0:
        print("No attendees to process. Exiting.")
        sys.exit(0)

    # Export to temporary CSV
    csv_filename = f"waitlist_{args.event_id}_temp.csv"
    export_to_csv(waitlist_attendees, csv_filename)
    print(f"Saved filtered list to {csv_filename}")
    
    print("\n--- Starting Newsletter Form Filling ---")
    
    # Validate workers
    if args.workers < 1:
        print("Error: Number of workers must be at least 1")
        return
    if args.workers > 20:
        print("Warning: Using more than 20 workers may cause issues. Limiting to 20.")
        args.workers = 20

    # Step 2: Process the CSV through the main form-filling logic
    asyncio.run(process_file(csv_filename, headless=not args.headed, workers=args.workers))
    
    # Step 3: Cleanup if not requested to keep
    if not args.keep_csv and os.path.exists(csv_filename):
        os.remove(csv_filename)
        print(f"\nCleaned up temporary file: {csv_filename}")
        
    print("\nAll tasks completed successfully!")

if __name__ == "__main__":
    main()
