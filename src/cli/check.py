import os, sys, json
from dotenv import load_dotenv

# Load env
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(base_dir, '.env'))

from src.eventbrite.fetcher import get_attendees

def check_event(event_id):
    attendees = get_attendees(event_id)
    if attendees is None:
        return
    
    unique_questions = set()
    for att in attendees:
        for ans in att.get('answers', []):
            q_text = ans.get('question', '')
            if q_text:
                unique_questions.add(q_text)
                
    with open('q_debug.json', 'w') as f:
        json.dump(list(unique_questions), f, indent=2)

if __name__ == '__main__':
    check_event('1984824961891')
