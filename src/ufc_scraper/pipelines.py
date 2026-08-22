# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import csv
import os
import re
from datetime import datetime, timezone

from PIL import Image

from ufc_scraper.items import EventItem, FighterItem, FightItem, EventAttendanceItem
from scrapy.exceptions import DropItem

# Event ids that pass the "/events/UFC-" URL filter but are not real UFC
# cards, e.g. small regional promotions whose name happens to collide.
NON_UFC_EVENT_IDS = {"27549", "28831", "12197", "63593", "61279"}
# Ultimate Fighter reality show episodes, not real UFC cards.
TUF_EPISODE_RE = re.compile(r"(Quarterfinals|Semifinals|Elimination|Wild ?Card|Opening Round|Preliminary)", re.I)
# Road to UFC is a real prospect series, checked first so it is never
# caught by the TUF pattern above.
ROAD_TO_UFC_RE = re.compile(r"Road to UFC", re.I)


class CleaningPipeline:
    """First pipeline stage. Validates each item (drops the ones that are
    not real UFC data) then normalises the rest, parsing raw strings into
    real dates, numbers and categories."""

    def process_item(self, item, spider):
        """Dispatches by item type. Each branch validates first, then
        normalises the raw fields it owns."""

        if isinstance(item, EventItem):
            # drop non-UFC events before they reach the CSV
            if self.is_excluded_event(item["event_id"], item["name"]):
                raise DropItem(f"Not a real UFC card: {item['name']}")

            item["date"] = self.parse_iso_date(item["date_raw"])

        elif isinstance(item, FightItem):
            # same exclusion check, fights inherit their event's status
            if self.is_excluded_event(item["event_id"], item["event_name"]):
                raise DropItem(f"Not a real UFC card: {item['event_name']}")

            item["event_date"] = self.parse_iso_date(item["event_date_raw"])
            item["method_category"], item["method_subtype"] = self.parse_method(item["method_raw"])

        elif isinstance(item, FighterItem):
            # fighter bios just need their raw fields normalised
            item["birth_date"] = self.parse_human_date(item["birth_date_raw"])
            item["height_cm"] = self.parse_height_cm(item["height_raw"])
            item["weight_kg"] = self.parse_weight_kg(item["weight_raw"])

        elif isinstance(item, EventAttendanceItem):
            item["date"] = self.parse_wiki_date(item["date_raw"])
            item["attendance"] = self.parse_attendance(item["attendance_raw"])
            if item["date"] is None:
                raise DropItem(f"Unparseable date: {item['date_raw']}")
        return item

    @staticmethod
    def is_excluded_event(event_id, name):
        """True if this event should not be treated as a real UFC card."""
        if event_id in NON_UFC_EVENT_IDS:
            return True
        if ROAD_TO_UFC_RE.search(name or ""):
            return False
        if TUF_EPISODE_RE.search(name or ""):
            return True
        return False

    @staticmethod
    def parse_iso_date(raw):
        """Sherdog's own dates already come as ISO strings, e.g. 2024-01-20."""
        if not raw:
            return None

        try:
            return datetime.fromisoformat(raw).date()
        except ValueError:
            return None

    @staticmethod
    def parse_human_date(raw):
        """Fighter birth dates are written like "Aug 15, 1990"."""
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%b %d, %Y").date()
        except ValueError:
            return None

    @staticmethod
    def parse_method(raw):
        """Splits "KO (Punch)" into category "KO" and subtype "Punch"."""
        if not raw:
            return None, None
        match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", raw.strip())

        if match:
            category = match.groups()[0]
            subtype = match.groups()[1]
            return category.strip(), subtype.strip()

        return raw.strip(), None

    @staticmethod
    def parse_height_cm(raw):
        """Height is written with both imperial and metric, e.g. 6'0" (183 cm).
        Only the metric number is kept."""
        if not raw:
            return None

        match = re.search(r"([\d.]+)\s*cm", raw)

        if not match:
            return None
        return float(match.groups()[0])

    @staticmethod
    def parse_weight_kg(raw):
        """Same idea as height, keep only the metric kg number."""
        if not raw:
            return None

        match = re.search(r"([\d.]+)\s*kg", raw)

        if not match:
            return None

        return float(match.groups()[0])

    @staticmethod
    def parse_wiki_date(raw):
        """Wikipedia writes dates as e.g. "Aug 15, 2026", a different format
        from Sherdog's ISO strings, so it needs its own parser."""
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%b %d, %Y").date()
        except ValueError:
            return None

    @staticmethod
    def parse_attendance(raw):
        """Missing values render as an em dash plus a screen-reader-only
        "N/a" span; ``get(default="").strip()`` in the spider already
        collapses that down to just the dash character."""
        if not raw:
            return None
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else None


class ImageMetadataPipeline:
    """Second pipeline stage, runs after Scrapy's own ImagesPipeline (which
    does the actual download). ImagesPipeline only records where the file
    landed and its checksum. This stage is what actually processes the
    downloaded file, opening it with Pillow to read real pixel dimensions
    and record size on disk, turning "a folder of JPEGs" into structured
    data that belongs in a CSV.
    """

    def process_item(self, item, spider):
        """Only fighters have portraits, everything else passes through."""
        if not isinstance(item, FighterItem):
            return item

        images = item.get("images") or []
        if not images:
            item["image_path"] = None
            item["image_width"] = None
            item["image_height"] = None
            item["image_kb"] = None
            return item

        info = images[0]
        item["image_path"] = info["path"]
        full_path = os.path.join(spider.settings.get("IMAGES_STORE"), info["path"])
        try:
            with Image.open(full_path) as im:
                item["image_width"], item["image_height"] = im.size
            item["image_kb"] = round(os.path.getsize(full_path) / 1024, 1)
        except (FileNotFoundError, OSError):
            item["image_width"] = item["image_height"] = item["image_kb"] = None

        return item


class CsvStoragePipeline:
    """Final pipeline stage, writes each item to its CSV. Which CSVs get
    opened depends on which spider is running, the `events` spider writes
    events/fights/fighters, `attendance` writes its own file. Opening every
    file unconditionally regardless of spider would mean running one spider
    truncates the other's output, so each spider only touches the files
    that hold the items it actually produces.
    """

    def open_spider(self, spider):
        """Called once when the spider starts. Opens only the CSVs this
        spider needs and writes their header row."""
        self.writers = {}

        if spider.name == "events":
            self.events_file = open("../data/events.csv", "w", newline="", encoding="utf_8")
            self.fights_file = open("../data/fights.csv", "w", newline="", encoding="utf_8")
            self.fighters_file = open("../data/fighters.csv", "w", newline="", encoding="utf_8")

            self.writers[EventItem] = csv.DictWriter(
                self.events_file, fieldnames = list(EventItem.fields.keys()), extrasaction="ignore"
            )
            self.writers[FightItem] = csv.DictWriter(
                self.fights_file, fieldnames = list(FightItem.fields.keys()), extrasaction="ignore"
            )
            # image_urls/images are Scrapy's own bookkeeping for the media
            # pipeline (a list of dicts), not something that belongs in a
            # flat CSV. The derived fields (image_path, image_width, ...)
            # are what's kept.
            fighter_fields = [f for f in FighterItem.fields if f not in ("image_urls", "images")]
            self.writers[FighterItem] = csv.DictWriter(
                self.fighters_file, fieldnames = fighter_fields, extrasaction="ignore"
            )

        elif spider.name == "attendance":
            self.attendance_file = open("../data/attendance.csv", "w", newline="", encoding="utf_8")
            self.writers[EventAttendanceItem] = csv.DictWriter(
                self.attendance_file, fieldnames = list(EventAttendanceItem.fields.keys()), extrasaction="ignore"
            )

        for writer in self.writers.values():
            writer.writeheader()

    def process_item(self, item, spider):
        """Looks up the right writer by the item's own class and writes
        one row. Items with no matching writer are left untouched."""
        writer = self.writers.get(type(item))
        if writer is not None:
            writer.writerow(dict(item))
        return item

    def close_spider(self, spider):
        """Called once when the spider finishes. Closes whichever files
        this spider actually opened."""
        for f in ("events_file", "fights_file", "fighters_file", "attendance_file"):
            if hasattr(self, f):
                getattr(self, f).close()



