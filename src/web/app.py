from flask import Flask, render_template, request, jsonify, Response
import asyncio
import os
from pathlib import Path
import json
import queue
import threading
from werkzeug.utils import secure_filename
from src.automation.form_submitter import process_file as async_process_file
from src.automation.form_submitter import FormEntry
import pandas as pd
from playwright.async_api import async_playwright
from src.eventbrite.fetcher import get_attendees, filter_waitlist_attendees
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
app = Flask(__name__, 
            template_folder=os.path.join(base_dir, 'templates'),
            static_folder=os.path.join(base_dir, 'static'))
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global queue for progress updates
progress_queue = queue.Queue()
current_status = {
    'processing': False,
    'total': 0,
    'completed': 0,
    'success': 0,
    'failed': 0,
    'current_message': ''
}


async def fill_form_worker_with_progress(worker_id: int, queue_obj: asyncio.Queue, results: dict, headless: bool = True):
    """Worker that processes form submissions with progress updates."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        form_url = "https://pub.s7.exacttarget.com/owhm5b4qtde"
        
        while True:
            try:
                entry = await asyncio.wait_for(queue_obj.get(), timeout=1.0)
                
                if entry is None:  # Poison pill
                    break
                
                try:
                    await page.goto(form_url, wait_until='networkidle')
                    await page.fill("input[name='First Name']", entry.first_name)
                    await page.fill("input[name='Last Name']", entry.last_name)
                    await page.fill("input[name='Email']", entry.email)
                    await page.click("button[type='submit']")
                    await page.wait_for_timeout(2000)
                    
                    results['success'].append(entry)
                    current_status['success'] += 1
                    current_status['completed'] += 1
                    current_status['current_message'] = f"✓ Successfully added {entry.first_name} {entry.last_name} to the newsletter"
                    progress_queue.put({
                        'type': 'success',
                        'message': f"✓ Successfully added {entry.first_name} {entry.last_name} to the newsletter",
                        'completed': current_status['completed'],
                        'total': current_status['total']
                    })
                    
                except Exception as e:
                    results['failed'].append((entry, str(e)))
                    current_status['failed'] += 1
                    current_status['completed'] += 1
                    current_status['current_message'] = f"✗ Error: {entry.first_name} {entry.last_name}"
                    progress_queue.put({
                        'type': 'error',
                        'message': f"✗ Error submitting {entry.first_name} {entry.last_name}: {str(e)}",
                        'completed': current_status['completed'],
                        'total': current_status['total']
                    })
                
                finally:
                    queue_obj.task_done()
                    
            except asyncio.TimeoutError:
                if queue_obj.empty():
                    await asyncio.sleep(0.1)
                continue
        
        await browser.close()


async def process_file_with_progress(file_path: str, workers: int = 10):
    """Process file with progress updates."""
    global current_status
    
    # Reset status
    current_status = {
        'processing': True,
        'total': 0,
        'completed': 0,
        'success': 0,
        'failed': 0,
        'current_message': 'Reading file...'
    }
    
    progress_queue.put({'type': 'info', 'message': 'Reading file...'})
    
    # Read file
    path = Path(file_path)
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(file_path)
    elif path.suffix.lower() in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
    else:
        progress_queue.put({'type': 'error', 'message': f'Unsupported file format: {path.suffix}'})
        current_status['processing'] = False
        return
    
    # Find columns (expecting specific headers)
    df.columns = df.columns.str.strip()
    first_name_col = 'first_name' if 'first_name' in df.columns else None
    last_name_col = 'last_name' if 'last_name' in df.columns else None
    email_col = 'email' if 'email' in df.columns else None
    
    if not all([first_name_col, last_name_col, email_col]):
        progress_queue.put({
            'type': 'error',
            'message': f'File must have headers: first_name, last_name, email. Available: {list(df.columns)}'
        })
        current_status['processing'] = False
        return
    
    # Filter data
    df_filtered = df[
        (df[first_name_col].notna()) &
        (df[last_name_col].notna()) &
        (df[email_col].notna()) &
        (~df[first_name_col].astype(str).str.contains("INFO REQUESTED", case=False, na=False)) &
        (~df[last_name_col].astype(str).str.contains("INFO REQUESTED", case=False, na=False)) &
        (~df[email_col].astype(str).str.contains("INFO REQUESTED", case=False, na=False))
    ].copy()
    
    current_status['total'] = len(df_filtered)
    progress_queue.put({
        'type': 'info',
        'message': f'Found {len(df_filtered)} valid entries (filtered from {len(df)} total rows)',
        'total': len(df_filtered)
    })
    
    if len(df_filtered) == 0:
        progress_queue.put({'type': 'error', 'message': 'No valid entries to process'})
        current_status['processing'] = False
        return
    
    # Create queue and results
    task_queue = asyncio.Queue()
    results = {'success': [], 'failed': []}
    
    # Populate queue
    for idx, row in df_filtered.iterrows():
        entry = FormEntry(
            first_name=str(row[first_name_col]).strip(),
            last_name=str(row[last_name_col]).strip(),
            email=str(row[email_col]).strip(),
            row_index=idx
        )
        await task_queue.put(entry)
    
    # Add poison pills
    for _ in range(workers):
        await task_queue.put(None)
    
    progress_queue.put({'type': 'info', 'message': f'Starting {workers} workers...'})
    
    # Create workers
    worker_tasks = [
        asyncio.create_task(fill_form_worker_with_progress(i, task_queue, results, headless=True))
        for i in range(workers)
    ]
    
    # Wait for completion
    await asyncio.gather(*worker_tasks)
    
    # Final status
    current_status['processing'] = False
    progress_queue.put({
        'type': 'complete',
        'message': f'Completed! {current_status["success"]} successful, {current_status["failed"]} failed',
        'success': current_status['success'],
        'failed': current_status['failed'],
        'total': current_status['total']
    })

async def process_event_with_progress(event_id: str, workers: int = 10):
    """Process attendees fetched via Eventbrite Event ID with progress updates."""
    global current_status
    
    # Reset status
    current_status = {
        'processing': True,
        'total': 0,
        'completed': 0,
        'success': 0,
        'failed': 0,
        'current_message': 'Fetching Eventbrite attendees...'
    }
    
    progress_queue.put({'type': 'info', 'message': f'Fetching attendees for Event ID: {event_id}...'})
    
    # Fetch attendees
    attendees = get_attendees(event_id)
    if attendees is None:
        progress_queue.put({'type': 'error', 'message': 'Failed to fetch attendees or API key is not configured.'})
        current_status['processing'] = False
        return

    progress_queue.put({'type': 'info', 'message': f'Total attendees fetched: {len(attendees)}. Filtering for waitlist/newsletter...'})
    
    waitlist_attendees = filter_waitlist_attendees(attendees)
    
    current_status['total'] = len(waitlist_attendees)
    progress_queue.put({
        'type': 'info',
        'message': f'Found {len(waitlist_attendees)} attendees who opted in.',
        'total': len(waitlist_attendees)
    })
    
    if len(waitlist_attendees) == 0:
        progress_queue.put({'type': 'error', 'message': 'No attendees found who opted in.'})
        current_status['processing'] = False
        return
        
    # Create queue and results
    task_queue = asyncio.Queue()
    results = {'success': [], 'failed': []}
    
    # Populate queue
    for idx, att in enumerate(waitlist_attendees):
        profile = att.get('profile', {})
        first_name = profile.get('first_name', '')
        last_name = profile.get('last_name', '')
        
        # Fallback if first_name/last_name are missing
        if not first_name and not last_name and profile.get('name'):
            parts = profile.get('name').split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''

        email = profile.get('email', '')
        
        # Skip 'INFO REQUESTED' dummy names if present
        if 'INFO REQUESTED' in first_name.upper() or 'INFO REQUESTED' in last_name.upper() or 'INFO REQUESTED' in email.upper():
            current_status['total'] -= 1
            continue

        entry = FormEntry(
            first_name=str(first_name).strip(),
            last_name=str(last_name).strip(),
            email=str(email).strip(),
            row_index=idx
        )
        await task_queue.put(entry)
    
    # Add poison pills
    for _ in range(workers):
        await task_queue.put(None)
    
    progress_queue.put({'type': 'info', 'message': f'Starting {workers} workers...'})
    
    # Create workers
    worker_tasks = [
        asyncio.create_task(fill_form_worker_with_progress(i, task_queue, results, headless=True))
        for i in range(workers)
    ]
    
    # Wait for completion
    await asyncio.gather(*worker_tasks)
    
    # Final status
    current_status['processing'] = False
    progress_queue.put({
        'type': 'complete',
        'message': f'Completed! {current_status["success"]} successful, {current_status["failed"]} failed',
        'success': current_status['success'],
        'failed': current_status['failed'],
        'total': current_status['total']
    })


def run_async_process(file_path: str, workers: int):
    """Run async process in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_file_with_progress(file_path, workers))
    finally:
        loop.close()

def run_async_event_process(event_id: str, workers: int):
    """Run async event process in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_event_with_progress(event_id, workers))
    finally:
        loop.close()


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get workers count from request
        workers = int(request.form.get('workers', 10))
        
        # Start processing in background thread
        thread = threading.Thread(target=run_async_process, args=(filepath, workers))
        thread.start()
        
        return jsonify({'success': True, 'message': 'Processing started'})

@app.route('/process_event', methods=['POST'])
def process_event():
    """Handle processing by Event ID."""
    event_id = request.form.get('event_id')
    if not event_id:
        return jsonify({'error': 'No Event ID provided'}), 400
    
    workers = int(request.form.get('workers', 10))
    
    # Start processing in background thread
    thread = threading.Thread(target=run_async_event_process, args=(event_id, workers))
    thread.start()
    
    return jsonify({'success': True, 'message': 'Processing started for event'})


@app.route('/progress')
def progress():
    """Server-sent events endpoint for progress updates."""
    def generate():
        while True:
            try:
                # Get update from queue with timeout
                update = progress_queue.get(timeout=1)
                yield f"data: {json.dumps(update)}\n\n"
            except queue.Empty:
                # Send heartbeat
                if not current_status['processing']:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            except:
                break
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/status')
def status():
    """Get current status."""
    return jsonify(current_status)

def run_server():
    import webbrowser
    import time
    
    # Open browser after short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://localhost:5000')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("=" * 60)
    print("Form Filler Application Starting...")
    print("Opening browser at http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    app.run(debug=False, host='127.0.0.1', port=5000)

if __name__ == '__main__':
    run_server()
