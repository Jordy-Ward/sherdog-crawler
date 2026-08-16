# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import csv
import re
from datetime import datetime, timezone

from ufc_scraper.items import EventItem, FighterItem, FightItem
from scrapy.exceptions import DropItem

NON_UFC_EVENT_IDS = {"27549", "28831", "12197", "63593", "61279"}
TUF_EPISODE_RE = re.compile(r"(Quarterfinals|Semifinals|Elimination|Wild ?Card|Opening Round|Preliminary)", re.I)
ROAD_TO_UFC_RE = re.compile(r"Road to UFC", re.I)


class CleaningPipeline:
    def process_item(self, item, spider):
        
        if isinstance(item, EventItem):
            
            if self.is_excluded_event(item["event_id"], item["name"]):
                raise DropItem(f"Not a real UFC card: {item['name']}")
            
            item["date"] = self.parse_iso_date(item["date_raw"])
            
        elif isinstance(item, FightItem):
            
            if self.is_excluded_event(item["event_id"], item["event_name"]):
                raise DropItem(f"Not a real UFC card: {item['event_name']}")
            
            item["event_date"] = self.parse_iso_date(item["event_date_raw"])
            item["method_category"], item["method_subtype"] = self.parse_method(item["method_raw"])
            
        elif isinstance(item, FighterItem):
            item["birth_date"] = self.parse_human_date(item["birth_date_raw"])
            item["height_cm"] = self.parse_height_cm(item["height_raw"])
            item["weight_kg"] = self.parse_weight_kg(item["weight_raw"])
        return item
    
    @staticmethod
    def is_excluded_event(event_id, name):
        if event_id in NON_UFC_EVENT_IDS:
            return True
        if ROAD_TO_UFC_RE.search(name or ""):
            return False
        if TUF_EPISODE_RE.search(name or ""):
            return True
        return False
    
    @staticmethod
    def parse_iso_date(raw):
        if not raw:
            return None
        
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError:
            return None
        
    @staticmethod
    def parse_human_date(raw):
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%b %d, %Y").date()
        except ValueError:
            return None
        
    @staticmethod
    def parse_method(raw):
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
        if not raw:
            return None
        
        match = re.search(r"([\d.]+)\s*cm", raw)
        
        if not match:
            return None
        return float(match.groups()[0])
    
    @staticmethod
    def parse_weight_kg(raw):
        if not raw:
            return None
        
        match = re.search(r"([\d.]+)\s*kg", raw)
        
        if not match:
            return None
        
        return float(match.groups()[0])
        
            

class CsvStoragePipeline:
    
    def open_spider(self, spider):

        self.events_file = open("../data/events.csv", "w", newline="", encoding="utf_8")
        self.fights_file = open("../data/fights.csv", "w", newline="", encoding="utf_8")
        self.fighters_file = open("../data/fighters.csv", "w", newline="", encoding="utf_8")
        
        self.events_writer = csv.DictWriter(
            self.events_file, fieldnames = list(EventItem.fields.keys()), extrasaction="ignore"
        )
        self.fights_writer = csv.DictWriter(
                    self.fights_file, fieldnames = list(FightItem.fields.keys()), extrasaction="ignore"
        )
        self.fighters_writer = csv.DictWriter(
                    self.fighters_file, fieldnames = list(FighterItem.fields.keys()), extrasaction="ignore"
        )
        self.events_writer.writeheader()
        self.fights_writer.writeheader()
        self.fighters_writer.writeheader()
    
    def process_item(self, item, spider):
        
        if isinstance(item, EventItem):
            self.events_writer.writerow(dict(item))
        elif isinstance(item, FightItem):
            self.fights_writer.writerow(dict(item))
        elif isinstance(item, FighterItem):
            self.fighters_writer.writerow(dict(item))
        
        return item
    
    def close_spider(self, spider):
        self.events_file.close()
        self.fights_file.close()
        self.fighters_file.close()



