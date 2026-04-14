import argparse
import time
import random
from typing import List, Dict
from urllib.parse import urljoin

import requests
from scrapy import Selector


URL = "https://nordot.app/-/units/{}"
BASE_URL = "https://nordot.app"
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'uk,en-US;q=0.9,en;q=0.8,ru;q=0.7,fr;q=0.6,nl;q=0.5,de;q=0.4,ja;q=0.3,es;q=0.2,it;q=0.1,pl;q=0.1,zh-CN;q=0.1,zh;q=0.1,ro;q=0.1,id;q=0.1',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Opera";v="122"',
    'sec-ch-ua-arch': '"x86"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.251", "Opera";v="122.0.5643.150"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"11.1.0"',
    'sec-ch-ua-wow64': '?0',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 OPR/122.0.0.0',
    'Cookie': 'display_language=en-US'
}


class NordotAppScraper:
    def __init__(
        self,
        url: str
    ):
        self.url = url
        self.base_url = BASE_URL
        self.headers = HEADERS
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_html(self, retries: int = 3, timeout: int = 20) -> str:
        """
        Fetch page HTML with a couple of retries + jitter.
        """
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(self.url, timeout=timeout)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                if attempt == retries:
                    raise
                time.sleep(random.uniform(0.5, 1.5))
        return ""

    def get_stories(self, html: str) -> List[Dict[str, str]]:
        """
        Extract titles and body text from the page.
        """
        sel = Selector(text=html)
        items = sel.xpath("//li[contains(@class,'articleList__item')]")

        stories = []
        body_text = None

        for li in items:
            story_id = li.xpath(".//a[@class='articleList__link']/@href").get()
            title = li.xpath(".//h2[@class='articleList__title articleList__title--noSub']/text()").get()
            story_url = urljoin(self.base_url, story_id) if story_id else ""

            if not story_id:
                continue

            print(title)
            resp = self.session.get(story_url, timeout=30)
            if resp.ok:
                story_sel = Selector(text=resp.text)
            body_text = ' '.join(story_sel.xpath("//article/p/text()").getall())

            if story_id:
                stories.append({
                    "title": title,
                    "body_text": body_text,
                })

        return stories

    def run(self):
        html = self.fetch_html()
        stories = self.get_stories(html)
        print(f"Stories number is {len(stories)}.")
        return stories

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=str)
    args = parser.parse_args()

    scraper = NordotAppScraper(
        url=URL.format(args.id)
    )
    stories = scraper.run()


if __name__ == "__main__":
    main()
