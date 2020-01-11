import datetime
import json
import logging
import time

import requests

API_WAIT_TIME = 3
API_MAX_ERRORS = 50
API_REFRESH_TIME = 5 * 60

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def create_session(api_key, outbound_date, inbound_date, origin_place, destination_place):
    url = "https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/v1.0"

    payload = "cabinClass=economy" \
              "&country=ES" \
              "&currency=EUR" \
              "&locale=es-ES" \
              f"&originPlace={origin_place}" \
              f"&destinationPlace={destination_place}" \
              f"&outboundDate={outbound_date}" \
              "&adults=1"

    if inbound_date:
        payload += f"&inboundDate={inbound_date}"

    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': api_key,
        'content-type': "application/x-www-form-urlencoded"
    }

    attempts = 0
    while True:
        try:
            response = requests.request("POST", url, data=payload, headers=headers)
            if response.text == '{}':
                break
            else:
                attempts += 1
                if attempts > API_MAX_ERRORS:
                    time.sleep(API_REFRESH_TIME)
        finally:
            time.sleep(API_WAIT_TIME)

    location = response.headers['Location'].split('/')[-1]
    return location


def get_place(api_key, place):
    url = "https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/autosuggest/v1.0/ES/EUR/es-ES/"
    querystring = {"query": place}
    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': api_key
    }
    response = requests.request("GET", url, headers=headers, params=querystring)
    response = json.loads(response.text)
    if 'Places' in response and response['Places'] and response['Places'][0]['CityId'] != '-sky':
        return response['Places'][0]['PlaceId']
    return None


def get_best_flight(itineraries, flights):
    best = None

    for itinerary in itineraries:
        out_id = itinerary['OutboundLegId']
        if 'InboundLegId' in itinerary:
            in_id = itinerary['InboundLegId']
        else:
            in_id = None

        if out_id not in flights or (in_id and in_id not in flights):
            continue

        for p in itinerary['PricingOptions']:
            if not best or p['Price'] < best[0]:
                airlines = set(flights[out_id])
                if in_id:
                    airlines.update(set(flights[in_id]))
                best = (
                    p['Price'],
                    airlines
                )

    return best


def fill_data(api_key, key):
    url = f"https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/uk2/v1.0/{key}"
    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': api_key
    }

    querystring = {"pageIndex": "0", "pageSize": "1000000", "stops": "1"}

    response = {}
    attempts = 0
    while 'Status' not in response or response['Status'] != 'UpdatesComplete':
        try:
            response = requests.request("GET", url, headers=headers, params=querystring)
        finally:
            time.sleep(API_WAIT_TIME)
        response = json.loads(response.text)
        attempts += 1
        if attempts > API_MAX_ERRORS:
            time.sleep(API_REFRESH_TIME)

    itineraries = response['Itineraries']
    legs = response['Legs']
    carriers = response['Carriers']

    return itineraries, legs, carriers


def poll_results(api_key, key):
    itineraries, legs, carriers = fill_data(api_key, key)

    airlines = {}
    for carrier in carriers:
        airlines[carrier['Id']] = carrier['Name']

    direct_flights, stops_flights = {}, {}
    for leg in legs:
        flights = tuple(airlines[x] for x in leg['Carriers'])
        if not leg['Stops']:
            direct_flights[leg['Id']] = flights
        else:
            stops_flights[leg['Id']] = flights

    best_direct = get_best_flight(itineraries, direct_flights)
    best_with_stops = get_best_flight(itineraries, stops_flights)

    return best_direct, best_with_stops


def search_one_way(api_key, query):
    current = query['start_date']
    end = query['end_date']
    sessions = []
    directs, with_stops = [], []

    while current <= end:
        key = create_session(
            api_key,
            str(current),
            None,
            query['origin'],
            query['destination']
        )
        sessions.append((key, current))
        logger.info(f"{current}")
        current += datetime.timedelta(days=1)

    for key, start in sessions:
        f1, f2 = poll_results(api_key, key)
        if f1:
            directs.append((start, *f1))
        if f2:
            with_stops.append((start, *f2))
        logger.info(f"{start}")

    directs.sort(key=lambda e: e[1])
    with_stops.sort(key=lambda e: e[1])
    return directs, with_stops


def search_round_trip(api_key, query):
    current = query['start_date']
    end = query['end_date']
    sessions = []
    directs, with_stops = [], []

    while current <= end:
        for i in range(query['min_days'], query['max_days'] + 1):
            key = create_session(
                api_key,
                str(current),
                current + datetime.timedelta(days=i),
                query['origin'],
                query['destination']
            )
            sessions.append((key, current, i))
            logger.info(f"{current} {i}")
        current += datetime.timedelta(days=1)

    for key, start, days in sessions:
        f1, f2 = poll_results(api_key, key)
        if f1:
            directs.append((start, days, *f1))
        if f2:
            with_stops.append((start, days, *f2))
        logger.info(f"{start} {days}")

    directs.sort(key=lambda e: e[2])
    with_stops.sort(key=lambda e: e[2])
    return directs, with_stops


def main():
    with open('config.json') as config:
        config = json.load(config)
        api_key = config['x-rapidapi-keys'][0]
        query = {
            'origin': get_place(api_key, 'Sofia'),
            'destination': get_place(api_key, 'Havana'),
            'start_date': datetime.date(2020, 4, 5),
            'end_date': datetime.date(2020, 4, 10),
            'min_days': 7,
            'max_days': 7
        }
        search_round_trip(api_key, query)


if __name__ == '__main__':
    main()
