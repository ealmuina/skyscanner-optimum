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
    if 'Places' in response and response['Places']:
        return response['Places'][0]['PlaceId']


def poll_results(config, key):
    url = f"https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/uk2/v1.0/{key}"

    querystring = {
        "pageIndex": "0",
        "pageSize": "1000",
        "stops": "0"
    }

    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': config['x-rapidapi-key']
    }

    response = {}

    while 'Status' not in response or response['Status'] != 'UpdatesComplete':
        time.sleep(1)
        try:
            response = requests.request("GET", url, headers=headers, params=querystring)
        except:
            continue
        response = json.loads(response.text)

    carriers = {}
    for carrier in response['Carriers']:
        if carrier['Id'] == 1011:
            continue
        carriers[carrier['Id']] = carrier['Name']

    direct_flights = {}
    for leg in response['Legs']:
        if not leg['Stops'] and leg['Carriers'][0] in carriers:
            direct_flights[leg['Id']] = carriers[leg['Carriers'][0]]

    best = None

    for itinerary in response['Itineraries']:
        out_id = itinerary['OutboundLegId']
        in_id = itinerary['InboundLegId']

        if out_id not in direct_flights or in_id not in direct_flights:
            continue

        for p in itinerary['PricingOptions']:
            if not best or p['Price'] < best[0]:
                best = (
                    p['Price'],
                    direct_flights[out_id],
                    direct_flights[in_id]
                )

    return best


def search_flights(config, query):
    current = query['start_date']
    end = query['end_date']
    sessions = []
    results = []

    while current < end:
        for i in range(query['min_days'], query['max_days'] + 1):
            key = create_session(
                config,
                str(current),
                current + datetime.timedelta(days=i),
                get_place(config, query['origin']),
                get_place(config, query['destination'])
            )
            sessions.append((key, current, i))
            print(current, i)
        current += datetime.timedelta(days=1)

    for key, start, days in sessions:
        flight = poll_results(config, key)
        entry = (start, days, *flight)

        results.append(entry)
        message = ' '.join(map(str, entry))

        if flight[0] < 600:
            message = '\033[92m' + message + '\033[0m'
        print(message)

    results.sort(key=lambda e: e[2])

    print('=============================')
    print(results[0])
    print('=============================')

    return results


if __name__ == '__main__':
    query = {
        'origin': 'Madrid',
        'destination': 'Havana',
        'start_date': datetime.date(2020, 4, 1),
        'end_date': datetime.date(2020, 5, 14),
        'min_days': 17,
        'max_days': 22
    }

    with open('config.json') as config:
        config = json.load(config)
        search_flights(config, query)
