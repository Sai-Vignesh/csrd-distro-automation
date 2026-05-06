import argparse
import asyncio
from pathlib import Path
import pandas as pd
from playwright.async_api import async_playwright
from dataclasses import dataclass
from typing import List


@dataclass
class FormEntry:
    """Data class for form entry."""
    first_name: str
    last_name: str
    email: str
    row_index: int


async def fill_form_worker(worker_id: int, queue: asyncio.Queue, results: dict, headless: bool = True):
    """Worker that processes form submissions from a queue."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        form_url = "https://pub.s7.exacttarget.com/owhm5b4qtde"
        
        while True:
            try:
                # Get entry from queue (with timeout to prevent hanging)
                entry = await asyncio.wait_for(queue.get(), timeout=1.0)
                
                if entry is None:  # Poison pill to stop worker
                    break
                
                try:
                    # Navigate to form
                    await page.goto(form_url, wait_until='networkidle')
                    
                    # Fill in the form fields
                    await page.fill("input[name='First Name']", entry.first_name)
                    await page.fill("input[name='Last Name']", entry.last_name)
                    await page.fill("input[name='Email']", entry.email)
                    
                    # Click submit button
                    await page.click("button[type='submit']")
                    
                    # Wait for confirmation
                    await page.wait_for_timeout(2000)
                    
                    results['success'].append(entry)
                    print(f"[Worker {worker_id}] ✓ Successfully added {entry.first_name} {entry.last_name} to the newsletter ({entry.email})")
                    
                except Exception as e:
                    results['failed'].append((entry, str(e)))
                    print(f"[Worker {worker_id}] ✗ Error submitting {entry.first_name} {entry.last_name}: {e}")
                
                finally:
                    queue.task_done()
                    
            except asyncio.TimeoutError:
                # No items in queue, check if we should continue
                if queue.empty():
                    await asyncio.sleep(0.1)
                continue
        
        await browser.close()


async def process_file(file_path: str, headless: bool = True, workers: int = 10):
    """Process the CSV/Excel file and fill forms in parallel."""
    # Read the file
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File {file_path} not found")
        return
    
    # Determine file type and read
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(file_path)
    elif path.suffix.lower() in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
    else:
        print(f"Error: Unsupported file format {path.suffix}")
        return
    
    # Normalize column names (case-insensitive)
    df.columns = df.columns.str.strip()
    
    # Find the relevant columns (expecting exact headers)
    first_name_col = 'first_name' if 'first_name' in df.columns else None
    last_name_col = 'last_name' if 'last_name' in df.columns else None
    email_col = 'email' if 'email' in df.columns else None
    
    if not all([first_name_col, last_name_col, email_col]):
        print("Error: Could not find required columns (first_name, last_name, email)")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Filter out rows with "INFO REQUESTED" or missing data
    df_filtered = df[
        (df[first_name_col].notna()) &
        (df[last_name_col].notna()) &
        (df[email_col].notna()) &
        (~df[first_name_col].astype(str).str.contains("INFO REQUESTED", case=False, na=False)) &
        (~df[last_name_col].astype(str).str.contains("INFO REQUESTED", case=False, na=False)) &
        (~df[email_col].astype(str).str.contains("INFO REQUESTED", case=False, na=False))
    ].copy()
    
    print(f"Found {len(df_filtered)} valid entries to process (filtered from {len(df)} total rows)")
    print(f"Using {workers} parallel workers\n")
    
    if len(df_filtered) == 0:
        print("No valid entries to process")
        return
    
    # Create queue and results dict
    queue = asyncio.Queue()
    results = {'success': [], 'failed': []}
    
    # Populate queue with entries
    for idx, row in df_filtered.iterrows():
        entry = FormEntry(
            first_name=str(row[first_name_col]).strip(),
            last_name=str(row[last_name_col]).strip(),
            email=str(row[email_col]).strip(),
            row_index=idx
        )
        await queue.put(entry)
    
    # Add poison pills for workers
    for _ in range(workers):
        await queue.put(None)
    
    # Create and start workers
    worker_tasks = [
        asyncio.create_task(fill_form_worker(i, queue, results, headless))
        for i in range(workers)
    ]
    
    # Wait for all workers to complete
    await asyncio.gather(*worker_tasks)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Completed: {len(results['success'])} successful, {len(results['failed'])} failed")
    
    if results['failed']:
        print(f"\nFailed entries:")
        for entry, error in results['failed']:
            print(f"  - {entry.first_name} {entry.last_name} ({entry.email}): {error}")
