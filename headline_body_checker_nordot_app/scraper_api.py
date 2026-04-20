import argparse
import time
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

API_URL = "https://nordot.app/-/units/{}/list"
HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
}

class NordotApiClient:
    def __init__(self, unit_id: str):
        self.unit_id = unit_id
        self.api_url = API_URL.format(unit_id)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _parse_date(self, date_str: str) -> datetime:
        """Helper to parse Nordot ISO dates into UTC aware objects."""
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))

    def fetch_posts(self, limit: int = 10, offset: int = 0) -> List[Dict]:
        params = {"offset": offset, "limit": limit}
        try:
            resp = self.session.get(self.api_url, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json().get("posts", [])
        except Exception as e:
            print(f"Error fetching batch: {e}")
            return []

    def run(self, 
            limit: Optional[int] = None, 
            start_date: Optional[datetime] = None, 
            end_date: Optional[datetime] = None):
        
        stories = []
        offset = 0
        chunk_size = 20
        
        print(f"Starting fetch for Unit {self.unit_id}...")
        if start_date and end_date:
            print(f"Filter: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        while True:
            batch = self.fetch_posts(limit=chunk_size, offset=offset)
            if not batch:
                break
            
            reached_end_of_range = False
            
            for post in batch:
                pub_date = self._parse_date(post.get("published_at"))
                
                if start_date and end_date:
                    if start_date <= pub_date <= end_date:
                        stories.append(self._format_story(post))
                    elif pub_date < start_date:
                        reached_end_of_range = True
                        break
                else:
                    stories.append(self._format_story(post))
                    if limit and len(stories) >= limit:
                        reached_end_of_range = True
                        break
            
            if reached_end_of_range:
                break
                
            offset += chunk_size
            print(f"Checked {offset} posts...")
            time.sleep(0.3)

        print(f"Finished. Total retrieved: {len(stories)}")
        return stories

    def _format_story(self, post: Dict) -> Dict:
        return {
            "id": post.get("id"),
            "title": post.get("title"),
            "body_text": post.get("body"),
            "published_at": post.get("published_at")
        }

def valid_date(s):
    """Parses string YYYY-MM-DD and makes it UTC aware."""
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Not a valid date: '{s}'. Expected YYYY-MM-DD.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=str, help="Nordot Unit ID")
    parser.add_argument("--limit", type=int, default=10, help="Number of stories (default 10)")
    parser.add_argument("--start", type=valid_date, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=valid_date, help="End date YYYY-MM-DD")
    
    args = parser.parse_args()

    client = NordotApiClient(unit_id=args.id)
    
    if args.start and args.end:
        adjusted_end = args.end.replace(hour=23, minute=59, second=59)
        stories = client.run(start_date=args.start, end_date=adjusted_end)
    else:
        stories = client.run(limit=args.limit)

    for s in stories:
        print(f"[{s['published_at']}] {s['title']}")

if __name__ == "__main__":
    main()