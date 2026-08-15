# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

"""Data schema for sherdog scraper
    
    Spider store data raw. Normalisation occurs in the pipeline
"""

import scrapy

class EventItem(scrapy.Item):
    """One ufc event is one row in events.csv"""
    
    event_id = scrapy.Field()
    name = scrapy.Field()
    date_raw = scrapy.Field()
    location_raw = scrapy.Field()
    
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()
    
class FightItem(scrapy.Item):
    """One fight is one row in fights.csv Wide"""
    
    ### identity
    fight_id = scrapy.Field() #created from event id and bout order. Sherdog has no fight ID
    event_id = scrapy.Field()
    event_name = scrapy.Field()
    event_date_raw = scrapy.Field()
    
    # two fighters of the fight
    fighter_a_id = scrapy.Field()
    fighter_a_name = scrapy.Field()
    fighter_b_id = scrapy.Field()
    fighter_b_name = scrapy.Field()
    
    # outcome
    # can be a win, draw, nc, unknown
    # winner id == fighter a or fighter b when outcome == win, otherwise empty
    
    outcome_type = scrapy.Field()
    winner_id = scrapy.Field()
    
    # fight details
    weight_class = scrapy.Field()
    is_title_fight = scrapy.Field()
    bout_order = scrapy.Field()
    is_main_event = scrapy.Field()
    referee = scrapy.Field()
    end_round = scrapy.Field()
    end_time = scrapy.Field()
    
    # method
    method_raw = scrapy.Field()
    
    # provenance where data came form 
    source_url = scrapy.Field()
    scraped_at = scrapy.Field() # when it was collected
    
    
class FighterItem(scrapy.Item):
    
    fighter_id = scrapy.Field()
    
    name = scrapy.Field()
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()
    
    birth_date_raw = scrapy.Field()
    nationality = scrapy.Field()
    height_raw = scrapy.Field()
    weight_raw = scrapy.Field()
    association = scrapy.Field()
    
    
    
    
    
    
    
    
    


    

