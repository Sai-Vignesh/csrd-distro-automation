import json
from src.eventbrite.fetcher import get_attendees

def extract_unique_questions(event_id, output_filename='unique_questions.json'):
    attendees = get_attendees(event_id)
    if not attendees:
        print("No attendees found.")
        return

    unique_questions = set()
    
    for att in attendees:
        answers = att.get('answers', [])
        for ans in answers:
            q_text = ans.get('question', '')
            if q_text:
                unique_questions.add(q_text)
                
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(list(unique_questions), f, indent=2)
        
    print(f"Unique questions saved to {output_filename}")
    return unique_questions

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract unique questions from Eventbrite attendees.")
    parser.add_argument("event_id", type=str, help="The ID of the Eventbrite event")
    parser.add_argument("--output", type=str, default="unique_questions.json", help="Output file name")
    args = parser.parse_args()
    
    extract_unique_questions(args.event_id, args.output)
