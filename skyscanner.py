import datetime
import json
import time

import requests


def create_session(config, outbound_date, inbound_date, origin_place, destination_place):
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
        'x-rapidapi-key': config['x-rapidapi-key'],
        'content-type': "application/x-www-form-urlencoded"
    }

    while True:
        try:
            response = requests.request("POST", url, data=payload, headers=headers)
            if response.text == '{}':
                break
            else:
                print(response.text)
        finally:
            time.sleep(3)

    location = response.headers['Location'].split('/')[-1]
    return location


def get_place(config, place):
    url = "https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/autosuggest/v1.0/ES/EUR/es-ES/"
    querystring = {"query": place}
    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': config['x-rapidapi-key']
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


def fill_data(config, key):
    url = f"https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/uk2/v1.0/{key}"
    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': config['x-rapidapi-key']
    }

    querystring = {"pageIndex": "0", "pageSize": "1000000", "stops": "1"}

    response = {}
    while 'Status' not in response or response['Status'] != 'UpdatesComplete':
        try:
            response = requests.request("GET", url, headers=headers, params=querystring)
        finally:
            time.sleep(1)
        response = json.loads(response.text)

    itineraries = response['Itineraries']
    legs = response['Legs']
    carriers = response['Carriers']

    return itineraries, legs, carriers


def poll_results(config, key):
    itineraries, legs, carriers = fill_data(config, key)

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


def search_one_way(config, query):
    current = query['start_date']
    end = query['end_date']
    sessions = []
    directs, with_stops = [], []

    while current <= end:
        key = create_session(
            config,
            str(current),
            None,
            query['origin'],
            query['destination']
        )
        sessions.append((key, current))
        print(current)
        current += datetime.timedelta(days=1)

    for key, start in sessions:
        f1, f2 = poll_results(config, key)
        if f1:
            directs.append((start, *f1))
        if f2:
            with_stops.append((start, *f2))

    directs.sort(key=lambda e: e[1])
    with_stops.sort(key=lambda e: e[1])
    return directs, with_stops


def search_round_trip(config, query):
    current = query['start_date']
    end = query['end_date']
    sessions = []
    directs, with_stops = [], []

    while current <= end:
        for i in range(query['min_days'], query['max_days'] + 1):
            key = create_session(
                config,
                str(current),
                current + datetime.timedelta(days=i),
                query['origin'],
                query['destination']
            )
            sessions.append((key, current, i))
            print(current, i)
        current += datetime.timedelta(days=1)

    for key, start, days in sessions:
        f1, f2 = poll_results(config, key)
        if f1:
            directs.append((start, days, *f1))
        if f2:
            with_stops.append((start, days, *f2))

    directs.sort(key=lambda e: e[1])
    with_stops.sort(key=lambda e: e[1])
    return directs, with_stops


if __name__ == '__main__':
    with open('config.json') as config:
        config = json.load(config)
        query = {
            'origin': get_place(config, 'Sofia'),
            'destination': get_place(config, 'Havana'),
            'start_date': datetime.date(2020, 4, 5),
            'end_date': datetime.date(2020, 4, 5),
            'min_days': 7,
            'max_days': 7
        }
        search_round_trip(config, query)
