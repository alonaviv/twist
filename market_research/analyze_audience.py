"""
Run with a python that has openpyxl installed.
Usage: python analyze_audience [order_data.xlsx]

Download a doc from lineup, filtering for as long as you can (a year I think) and for שולם and מומש
Export the following fields (in this order):
לקוח - שם פרטי
לקוח - שם משפחה
שם המוצר
תכונות המוצר - מק״ט
תכונות המוצר - כמות


Remember to not use events that are currently in the process of being sold!! Incomplete data. Have an exclude list
for this (though sometimes you do want this data)

Need to make adjustments to the script if you want to use several files (since lineup only lets you filter and
download a file for max span of a year)

Looking at people who are strictly audience. If there were a singer at any time, removing them from the accounting
completely
"""
import sys
import re
from openpyxl import load_workbook
from dataclasses import dataclass, field
from collections import defaultdict
from pprint import pprint
from datetime import datetime

ATTN_SKU = 'ATTN'
SINGER_SKU = 'SING'

def sort_events(event_key):
    date_match = re.search(r'(\d{1,2}\.\d{1,2})', event_key)
    date_str = date_match.group(1)
    date_obj = datetime.strptime(date_str, "%d.%m")
    return date_obj


EXCLUDE_EVENTS = [
    'Broadway With a Twist', # QA night at our house
    # Currently being sold
    # 'Broadway With a Twist - 3.11 - Babu Bar - Tel Aviv',
    # 'Broadway With a Twist - 10.11 - Babu Bar - Tel Aviv',
    # 'Broadway With a Twist - 24.11 - Babu Bar - Tel Aviv',
]

@dataclass
class AudeinceCustomerCounter:
    events: list = field(default_factory=list)
    num_times_ordered: int = 0
    total_tickets: int = 0
    was_singer: bool = None

counters = defaultdict(AudeinceCustomerCounter)
recurring_orders = defaultdict(int)
audience_per_event = defaultdict(int)

# TODO: Something seems off
# TODO: 1. If there are about 23 single timers in each event, what with the other audience members? Aren't enough repeat comers for that
# TODO": 2. Some of the repeat comers show the same date twice. 2 different orders for same event? Need to account for that.

EVENT = 'Broadway With a Twist - 29.9 - Friends Underground Bar - Tel Aviv'

if __name__ == "__main__":
    path = sys.argv[1]
    worksheet = load_workbook(path).active
    for row in worksheet.iter_rows(min_row=2, values_only=2):
        first_name, last_name, event_name, ticket_type, total_tickets = row
        name = f"{first_name} {last_name}"
        if ticket_type == ATTN_SKU and name != "אלון אביב" and event_name not in EXCLUDE_EVENTS:
            counters[name].num_times_ordered += 1
            counters[name].total_tickets += total_tickets
            counters[name].events.append(event_name)
            audience_per_event[event_name] += total_tickets

        if ticket_type == SINGER_SKU and name in counters:
            counters[name].was_singer = True

    # Delete those who were singers
    counters = {name: counter for name, counter in counters.items() if not counter.was_singer}

    for name, counter in counters.items():
        if counter.was_singer:
            del counters[name]

    for counter in counters.values():
        recurring_orders[counter.num_times_ordered] += 1

    print(f"""
Analyzing {len(audience_per_event)} BWT events.
Total audience orders: {sum(counter.num_times_ordered for counter in counters.values())}
Total audience tickets (each order can heve several tickets): {sum(counter.total_tickets for counter in counters.values())}
Total people that ever ordered an audience ticket: {len(counters)}
""")

    for amount_ordered, num_people in sorted(recurring_orders.items()):
        print(f"Amount of people that ordered audience tickets for {amount_ordered} events: {num_people}")

    events_with_single_comers = defaultdict(list)
    for name, counter in counters.items():
        if counter.num_times_ordered == 1:
            [event] = counter.events
            events_with_single_comers[event].append((name, counter))


    print("\nHow many single comers each event had:")
    for event, num_single_comers in sorted(events_with_single_comers.items(), key=lambda item: sort_events(item[0]),
                                           reverse=True):
        print(f"Event {event}: {num_single_comers}")


    print("\nThe events that repeated comers came to")
    for name, counter in counters.items():
        if counter.num_times_ordered > 1:
            print(f"{name} - Ordered {counter.num_times_ordered} times: {counter.events}")





