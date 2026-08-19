import scrapy

from ufc_scraper.items import EventAttendanceItem
from datetime import datetime, timezone


class AttendanceSpider(scrapy.Spider):
    """third parser. Wikipedia's UFC events page
    keeps one wikitable with attendance figures for every card the promotion
    has run
    """

    name = "attendance"
    allowed_domains = ["en.wikipedia.org"]
    start_urls = ["https://en.wikipedia.org/wiki/List_of_UFC_events"]

    def parse(self, response):
        now = datetime.now(timezone.utc).isoformat()

        tables = response.css("table.wikitable")
        target = None
        for table in tables:
            headers = table.css("th::text").getall()
            if any("Attendance" in h for h in headers):
                target = table
                break

        if target is None:
            self.logger.error("Could not find the attendance wikitable")
            return

        for row in target.css("tbody tr"):
            cells = row.css("td")
            if len(cells) < 6:
                continue 

            item = EventAttendanceItem()
            item["event_name_raw"] = cells[1].css("::text").get(default="").strip()
            item["date_raw"] = cells[2].css("::text").get(default="").strip()
            item["venue"] = cells[3].css("::text").get(default="").strip()
            item["location_raw"] = " ".join(
                t.strip() for t in cells[4].css("::text").getall() if t.strip()
            )
            item["attendance_raw"] = cells[5].css("::text").get(default="").strip()

            item["source_url"] = response.url
            item["scraped_at"] = now
            yield item
