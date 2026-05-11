import requests
import sys
import json
import csv
import os

BASE_URL = "https://www.eventbriteapi.com/v3"

def get_attendees(event_id):
    attendees = []
    has_more_items = True
    continuation = None

    api_key = os.environ.get("EVENTBRITE_API_KEY")
    if not api_key:
        print("Error: EVENTBRITE_API_KEY environment variable is not set.", file=sys.stderr)
        return None

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    print(f"Fetching attendees for event {event_id}...")

    while has_more_items:
        params = {}
        if continuation:
            params['continuation'] = continuation
            
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/attendees/",
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            print(f"Error: API request failed with status code {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            return None

        data = response.json()
        if 'attendees' in data:
            attendees.extend(data['attendees'])
        else:
            print("No attendees found in response or unexpected format.", file=sys.stderr)
            return None

        pagination = data.get('pagination', {})
        has_more_items = pagination.get('has_more_items', False)
        continuation = pagination.get('continuation')

    return attendees

def filter_waitlist_attendees(attendees):
    waitlist_attendees = []
    
    for attendee in attendees:
        answers = attendee.get('answers', [])
        is_waitlist = False
        
        for answer in answers:
            q_text = answer.get('question', '').lower()
            a_text = answer.get('answer', '').lower()
            
            # Look for questions related to waitlist, email distro list, or newsletter
            keywords = ['waitlist', 'email list', 'distro', 'newsletter', 'subscribe', 'mailing list', 'updates']
            if any(kw in q_text for kw in keywords):
                # Check for an affirmative answer
                if a_text in ['yes', 'y', 'true', '1'] or 'yes' in a_text.split() or 'yes,' in a_text:
                    is_waitlist = True
                    break
                
        if is_waitlist:
            waitlist_attendees.append(attendee)

    return waitlist_attendees

def export_to_csv(attendees, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        # Define some basic fields to extract
        fieldnames = ['id', 'first_name', 'last_name', 'email', 'ticket_class_name', 'status', 'created']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        if not attendees:
            return
            
        for att in attendees:
            profile = att.get('profile', {})
            
            # Eventbrite generally provides first_name and last_name, but if not we can try splitting 'name'
            first_name = profile.get('first_name', '')
            last_name = profile.get('last_name', '')
            
            if not first_name and not last_name and profile.get('name'):
                parts = profile.get('name').split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''

            writer.writerow({
                'id': att.get('id', ''),
                'first_name': first_name,
                'last_name': last_name,
                'email': profile.get('email', ''),
                'ticket_class_name': att.get('ticket_class_name', ''),
                'status': att.get('status', ''),
                'created': att.get('created', '')
            })
