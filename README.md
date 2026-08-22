# UFC Fight Analysis

Sherdog UFC crawler
Wiki scraper

## Research questions

1. How has the way fights end shifted over time?
2. Within submissions, has the technique mix changed?
3. Does time off between fights hurt performance?
4. When do fighters peak?
5. Is there a home country advantage?
6. Do bigger crowds see more finishes?
7. Which active fighters never let a fight reach the judges?
8. How accurately can a simple pre-fight rule call a fight?

## Data

- `events.csv` All UFC events
- `fights.csv` All UFC fights
- `fighters.csv` All UFC fighters that have fought in an event
- `attendance.csv` Attendance per event from wiki
- `data/images/`: downloaded fighter portraits sherdog, gitignored

## Structure

```
src/ufc_scraper/
  items.py         four items: EventItem, FightItem, FighterItem, EventAttendanceItem
  spiders/
    events.py       main crawler, Sherdog sitemaps -> events -> fighters -> back to events
    attendance.py    Wikipedia's "List of UFC events"
  pipelines.py     CleaningPipeline (validate, normalise) -> ImagesPipeline (download
                   portraits) -> ImageMetadataPipeline (Pillow dimensions/size) ->
                   CsvStoragePipeline (write CSVs)
  settings.py      robots.txt obeyed, AutoThrottle, custom user agent

notebooks/analysis.ipynb   all analysis and figures
report/report.tex          the report
```
