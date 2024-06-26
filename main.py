#!/usr/bin/env python3
import os.path
import re
import sys
import csv
import urllib.request
from datetime import datetime

# Base url for the mazamas csv calendar
CAL_URL = "https://mazamas.org/calendar/csv/"
# Ignore some fields so the output is easier to handle
IGNORE_FIELDS = {"Activity Notes", "Assistant"}

# Activity Types: {'Hike Route', 'Other', 'Field Session', 'Climb Route', 'Lecture',
#                  'Snowshoe', 'Partner Event', 'Meeting', 'Course'}
IGNORE_ACTIVITY_TYPES = {'Field Session', 'Lecture', 'Meeting', 'Hike Route', 'Ski Mountaineering Route'}

ACTIVITY_TYPE_ORDER = ["Course", "Hike Route", "Snowshoe", "Climb Route"]

# Common date format
DATE_FORMAT = "%Y-%m-%d"

NOT_INTERESTED_FILE = "not_interested.txt"

# Columns to reference directly
ACTIVITY_TYPE = 'Activity Type'
ACTIVITY_NAME = 'Activity Name'
START_DATE = 'Start Date'
LEADER = 'Leader'
PACE = 'Pace'
GRADE = 'Grade'
REG_CLOSE_DATE = 'Reg. Close Date'
REG_OPEN_DATE = 'Reg. Open Date'
TEAM_SIZE = 'Team Size'
NUMBER_OF_OPENINGS = 'Number of openings'

# We can't just use _now_ as now > today (since the hours come into play) so this basically rounds
#  the date down to just the day
TODAY = datetime.strptime(datetime.strftime(datetime.now(), DATE_FORMAT), DATE_FORMAT)


def get_csv_url(current_datetime):
    """
    Get the calendar csv directly from their website by building a URL
    :return: List of csv entries (not parsed)
    """

    # noinspection PyListCreation
    options = []
    # No idea what this does
    options.append("bucket=All")
    # 90 days into the future, 90 is the max
    options.append("days=90")
    options.append("start_date=" + current_datetime.strftime(DATE_FORMAT))

    url = CAL_URL + "?" + "&".join(options)
    print(f'Fetching url {url}')
    response = urllib.request.urlopen(url)
    lines = [line.decode('utf-8') for line in response.readlines()]
    with open('out.csv', 'w') as fh:
        fh.writelines(lines)
    return lines


def get_csv_file():
    """
    Get the calendar csv from a local csv file. This is mostly for development as hitting their
    website directly would greatly slow down progress.
    :return: List of csv entries (not parsed)
    """
    print("Reading out.csv")
    with open("out.csv") as fh:
        return fh.readlines()


def is_past(date_str):
    """
    Check if the given string is past our current time
    :param date_str: The date we are checking as a string
    :return: True if NOW is greater than the given date
    """
    if date_str is None or date_str == '':
        return False

    return TODAY > datetime.strptime(date_str, DATE_FORMAT)


def is_full(event):
    number_of_openings_str = event[NUMBER_OF_OPENINGS]
    if number_of_openings_str is None or number_of_openings_str == '':
        return True
    number_of_openings = float(number_of_openings_str)
    return number_of_openings <= 0


def read_csv(fetcher):
    """
    Fetch the csv data and parse it into a list of events, with each event being represented
    by a simple dictionary.
    :param fetcher: Function to run to fetch the csv data
    :return: List of events, with each event being represented by a simple dictionary
    """
    # Run the fetcher and get the data to process
    data = fetcher(datetime.now())

    # Either the CSV is not showing all the data for an event (like the link id) or there is a rendering
    # bug on the website, but it appears possible for the same leader to have two different events in the
    # same category on the same day and have only one of them appear on the web site.  To try to handle
    # this I'm going to alert if we see a possible double schedule.
    event_map = {}

    headers = None
    events = []
    reader = csv.reader(data)
    for row in reader:
        if headers is None:
            headers = row
        else:
            event = {}
            for i in range(0, len(row)):
                if headers[i] in IGNORE_FIELDS:
                    continue
                event[headers[i]] = row[i]
            # Skip any activities we don't care about
            if event[ACTIVITY_TYPE] in IGNORE_ACTIVITY_TYPES:
                continue
            key = event[ACTIVITY_TYPE] + ":" + event[START_DATE] + ":" + event[LEADER]
            if key in event_map:
                print("ALERT - Duplicate activity/event/leader %s" % key)
                print("\t%s" % event_map[key])
                print("\t%s" % event[ACTIVITY_NAME])
            else:
                event_map[key] = event[ACTIVITY_NAME]
            # Don't show events which are already closed
            if is_past(event[REG_CLOSE_DATE]):
                continue
            # Don't show events which are not yet open
            # if event[REG_OPEN_DATE] is None or event[REG_OPEN_DATE] == '':
            #     continue
            # Don't bother showing events which are already filled up
            if is_full(event):
                continue
            # Don't show BCEP events
            if event[ACTIVITY_NAME].startswith('BCEP'):
                continue
            events.append(event)
    return events


def print_all_activity_types(events):
    """
    Given the list of events, return a unique set of activities.  This was mostly a debugging tool.
    :param events: The list of events to get the activity types from
    :return: Set of all activity types
    """
    # find all activity types
    activity_types = set()
    for event in events:
        activity_type = event[ACTIVITY_TYPE]
        activity_types.add(activity_type)
    print(f'Activity Types: {activity_types}')


def print_events_by_type(events, by_open=False):

    # Group by type
    activity_types = {}
    for event in events:
        if event[ACTIVITY_TYPE] in activity_types:
            activity_types[event[ACTIVITY_TYPE]].append(event)
        else:
            activity_types[event[ACTIVITY_TYPE]] = [event]

    # Print in the order of the ACTIVITY_TYPE_ORDER
    seen = {}
    for activity_type in ACTIVITY_TYPE_ORDER:
        if activity_type not in activity_types:
            continue
        seen[activity_type] = True
        print(activity_type)
        print_events(activity_types[activity_type], by_open)
        print()

    # Print out any stragglers
    for activity_type in activity_types:
        if activity_type in seen:
            continue
        print(activity_type)
        print_events(activity_types[activity_type], by_open)
        print()


def print_events(events, by_open=False):

    if by_open:
        events.sort(key=lambda x: f"{x[REG_OPEN_DATE]} {x[START_DATE]}")
        # print(events)
    for event in events:
        open_reg = "       "
        if event[REG_OPEN_DATE] is None or event[REG_OPEN_DATE] == '':
            open_reg = "  N/O  "
        elif not is_past(event[REG_OPEN_DATE]):
            open_reg = '- '+event[REG_OPEN_DATE][5:]
        pace = event[PACE]
        if pace is None or pace == '':
            pace = '?'

        print(f'\t{event[START_DATE]} {open_reg} - {event[ACTIVITY_NAME]} - {pace}/{event[GRADE]} - {event[LEADER]}')


def read_not_interested():

    # Specific events we are not interested in
    events = {}

    # Dates we are busy
    dates = set()

    if not os.path.exists(NOT_INTERESTED_FILE):
        return events, dates

    single_date = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    date_range = re.compile(r'^(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})$')

    # Read the entire file into a list
    with open(NOT_INTERESTED_FILE) as fh:
        data = fh.readlines()

    activity_type = None
    for line in data:
        is_event = line.startswith(" ")
        line = line.strip()

        # Skip blank lines
        if len(line) == 0:
            continue

        # Skip comments
        if line.startswith("#"):
            # Ignore comments
            continue

        if is_event:
            if activity_type is None:
                print("Can't have an event without a type: %s", line)
                continue
            events[activity_type].append(line)
            continue

        # This is either an activity heading, or a specific date
        if single_date.match(line) is not None:
            dates.add(line)
            continue

        match = date_range.match(line)
        if match is not None:
            start_date = match.group(1)
            end_date = match.group(2)
            add_dates(start_date, end_date, dates)

        activity_type = line
        if activity_type not in events:
            events[activity_type] = []

    return events, dates


def add_dates(start_date, end_date, dates):
    y1, m1, d1 = [int(a) for a in start_date.split('-')]
    y2, m2, d2 = [int(a) for a in end_date.split('-')]

    # Hacky way to find dates between x and y
    # Yes, not all months have 31 days, but for this it doesn't matter
    while True:
        date = f"{y1}-{m1:02}-{d1:02}"
        dates.add(date)
        d1 += 1
        if d1 > 31:
            d1 = 1
            m1 += 1
        if m1 > 12:
            m1 = 1
            y1 += 1
        if y1 == y2 and m1 == m2 and d1 > d2:
            break


def filter_events(events, not_interested, bad_dates):
    filtered = []
    for event in events:
        activity_type = event[ACTIVITY_TYPE]
        start_date = event[START_DATE]
        leader = event[LEADER]
        if start_date in bad_dates:
            # print("Bad date %s %s %s" % (activity_type, start_date, leader))
            continue

        # Create the key
        key = start_date + " : " + leader
        if activity_type in not_interested and key in not_interested[activity_type]:
            # print("Skipping %s %s %s" % (activity_type, start_date, leader))
            continue

        filtered.append(event)

    return filtered


def main(args):

    # Read the file of hikes we are not interested in
    not_interested, bad_dates = read_not_interested()

    by_open = len(args) == 2 and args[1] == "-reg"
    events = read_csv(get_csv_url)
    # events = read_csv(get_csv_file)

    # Filter events for not interested
    if len(not_interested) > 0:
        events = filter_events(events, not_interested, bad_dates)
        print()

    print_events_by_type(events, by_open)
    # for event in events:
    #     print(event)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main(sys.argv)
