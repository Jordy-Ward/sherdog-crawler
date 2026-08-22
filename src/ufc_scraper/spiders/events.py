import re
from datetime import datetime, timezone

import scrapy

from ufc_scraper.items import EventItem, FightItem, FighterItem


class EventsSpider(scrapy.Spider):
    name = "events"
    allowed_domains = ["sherdog.com"]
    
    SITEMAPS = [
        "https://www.sherdog.com/sitemap-events.xml",
        "https://www.sherdog.com/sitemap-events2.xml",
        "https://www.sherdog.com/sitemap-events3.xml",
        "https://www.sherdog.com/sitemap-events4.xml",

    ]
    
    # spiders start up config to limit how many events it follows from the sitemap
    def __init__(self, limit=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit = int(limit) if limit else None
        self.queued = 0

    # starting point for the crawler
    async def start(self):
        for url in self.SITEMAPS:
            yield scrapy.Request(url, callback=self.parse_sitemap)


    def parse_sitemap(self, response):
        response.selector.remove_namespaces()
        for loc in response.xpath("//loc/text()").getall():
            if "/events/UFC-" not in loc:
                continue
            if self.limit is not None and self.queued >= self.limit:
                return
            self.queued += 1
            yield response.follow(loc, callback=self.parse_event)

    def parse_event(self, response):
        event_id = re.search(r"-(\d+)$", response.url).group(1)
        event_name = response.css("h1 span[itemprop='name']::text").get()
        event_date = response.css("meta[itemprop='startDate']::attr(content)").get()
        now = datetime.now(timezone.utc).isoformat()

        # --- one EventItem describing the event itself ---
        event = EventItem()
        event["event_id"] = event_id
        event["name"] = event_name
        event["date_raw"] = event_date
        event["location_raw"] = response.css(
            "meta[itemprop='location']::attr(content)"
        ).get()
        event["source_url"] = response.url
        event["scraped_at"] = now
        yield event

        # --- one FightItem per undercard fight ---
        for row in response.css("table.new_table.result tr")[1:]:
            
            left = row.css("div.fighter_list.left")
            right = row.css("div.fighter_list.right")

            fighter_a_id = left.css("a::attr(href)").re_first(r"-(\d+)$")
            fighter_b_id = right.css("a::attr(href)").re_first(r"-(\d+)$")
            bout_order = row.css("td:first-child::text").re_first(r"\d+")

            outcome_type, winner_id = self.decide_outcome(
                left.css("span.final_result::text").get(),
                right.css("span.final_result::text").get(),
                fighter_a_id,
                fighter_b_id,
            )

            cells = row.css("td")
            # A well-formed fight row has 7 cells; anything shorter is a
            # cancelled/malformed
            if len(cells) < 2:
                continue

            item = FightItem()
            item["fight_id"] = f"{event_id}-{bout_order}"
            item["event_id"] = event_id
            item["event_name"] = event_name
            item["event_date_raw"] = event_date

            item["fighter_a_id"] = fighter_a_id
            item["fighter_a_name"] = " ".join(
                left.css("span[itemprop='name']::text").getall()
            )
            item["fighter_b_id"] = fighter_b_id
            item["fighter_b_name"] = " ".join(
                right.css("span[itemprop='name']::text").getall()
            )

            item["outcome_type"] = outcome_type
            item["winner_id"] = winner_id

            item["weight_class"] = row.css("span.weight_class::text").get()
            item["is_title_fight"] = bool(row.css("span.title_fight").get())
            item["bout_order"] = bout_order
            item["is_main_event"] = False
            item["referee"] = row.css("td.winby a::text").get()
            item["end_round"] = cells[-2].css("::text").get()
            item["end_time"] = cells[-1].css("::text").get()
            item["method_raw"] = row.css("td.winby b::text").get()

            item["source_url"] = response.url
            item["scraped_at"] = now
            yield item
            
            for href in (left.css("a::attr(href)").get(), right.css("a::attr(href)").get()):
                if href:
                    yield response.follow(href, callback=self.parse_fighter)

        # --- the main event is its own mark up in css on the event page so must parse differently
        # Upcoming events still render div.fight_card (the announced matchup)
        # but have no fight_card_resume, since there is no result yet. Requiring
        # the resume cells skips those cleanly instead of raising IndexError.
        card = response.css("div.fight_card")
        cells = response.css("table.fight_card_resume td")
        if card and len(cells) >= 5:
            left = card.css("div.fighter.left_side")
            right = card.css("div.fighter.right_side")

            def cell(i):
                """Value of resume cell i, dropping its <em> label."""
                parts = [t.strip() for t in cells[i].css("::text").getall() if t.strip()]
                return " ".join(parts[1:]) if len(parts) > 1 else ""

            fighter_a_id = left.css("a::attr(href)").re_first(r"-(\d+)$")
            fighter_b_id = right.css("a::attr(href)").re_first(r"-(\d+)$")
            bout_order = cell(0)

            outcome_type, winner_id = self.decide_outcome(
                left.css("span.final_result::text").get(),
                right.css("span.final_result::text").get(),
                fighter_a_id,
                fighter_b_id,
            )

            item = FightItem()
            item["fight_id"] = f"{event_id}-{bout_order}"
            item["event_id"] = event_id
            item["event_name"] = event_name
            item["event_date_raw"] = event_date

            item["fighter_a_id"] = fighter_a_id
            item["fighter_a_name"] = " ".join(
                left.css("h3 span[itemprop='name']::text").getall()
            )
            item["fighter_b_id"] = fighter_b_id
            item["fighter_b_name"] = " ".join(
                right.css("h3 span[itemprop='name']::text").getall()
            )

            item["outcome_type"] = outcome_type
            item["winner_id"] = winner_id

            item["weight_class"] = card.css("span.weight_class::text").get()
            item["is_title_fight"] = bool(card.css("span.title_fight").get())
            item["bout_order"] = bout_order
            item["is_main_event"] = True
            item["referee"] = cell(2)
            item["end_round"] = cell(3)
            item["end_time"] = cell(4)
            item["method_raw"] = cell(1)

            item["source_url"] = response.url
            item["scraped_at"] = now
            yield item
            
            for href in (left.css("a::attr(href)").get(), right.css("a::attr(href)").get()):
                if href:
                    yield response.follow(href, callback=self.parse_fighter)

    # parse the fighters BIO
    def parse_fighter(self, response):
        fighter_id = re.search(r"-(\d+)$", response.url.rstrip("/")).group(1)
        now = datetime.now(timezone.utc).isoformat()

        item = FighterItem()
        item["fighter_id"] = fighter_id
        item["name"] = response.css("h1[itemprop='name'] ::text").get()
        item["birth_date_raw"] = response.css("[itemprop='birthDate']::text").get()
        item["nationality"] = response.css("[itemprop='nationality']::text").get()
        item["height_raw"] = " ".join(
            t.strip() for t in
            response.xpath("//td[b[@itemprop='height']]//text()").getall()
            if t.strip()
        )
        item["weight_raw"] = " ".join(
            t.strip() for t in
            response.xpath("//td[b[@itemprop='weight']]//text()").getall()
            if t.strip()
        )
        item["association"] = response.css(
            "div.association-class [itemprop='name']::text"
        ).get()
        # Sherdog serves the portrait as a relative /image_crop/... path
        # join agaisnt the url and then fetch it 
        portrait = response.css("img[itemprop='image']::attr(src)").get()
        item["image_urls"] = [response.urljoin(portrait)] if portrait else []

        item["source_url"] = response.url
        item["scraped_at"] = now
        yield item

        # Follow only the UFC tagged rows so we doont go into other regional promotions. 
        # makes the graph ultimately end!!!
        pro_table = response.xpath(
            "//div[contains(@class,'slanted_title') and contains(., 'FIGHT HISTORY - PRO')]"
            "/../following-sibling::div[contains(@class,'module fight_history')][1]"
        )
        for row in pro_table.css("tr")[1:]:
            event_href = row.css("td:nth-child(3) a::attr(href)").get()
            if not event_href or "/events/UFC-" not in event_href:
                continue
            yield response.follow(event_href, callback=self.parse_event)
            opp_href = row.css("td:nth-child(2) a::attr(href)").get()
            if opp_href:
                yield response.follow(opp_href, callback=self.parse_fighter)

    @staticmethod
    def decide_outcome(a_res, b_res, a_id, b_id):
        """Map the two fighters' result labels onto (outcome_type, winner_id).

        Anything unrecognised becomes "unknown" rather than a guess, so that
        draws / no-contests we haven't seen yet show up in the data instead of
        being silently mislabelled.
        """
        a_res = (a_res or "").strip().lower()
        b_res = (b_res or "").strip().lower()
        if a_res == "win":
            return "win", a_id
        if b_res == "win":
            return "win", b_id
        if "draw" in a_res or "draw" in b_res:
            return "draw", ""
        if a_res in ("nc", "no contest") or b_res in ("nc", "no contest"):
            return "nc", ""
        return "unknown", ""

