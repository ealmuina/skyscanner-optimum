import datetime
import json
import time

import requests


def create_session(outbound_date, inbound_date):
    url = "https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/v1.0"

    payload = f"inboundDate={inbound_date}" \
              "&cabinClass=economy" \
              "&country=ES" \
              "&currency=EUR" \
              "&locale=es-ES" \
              "&originPlace=MAD-sky" \
              "&destinationPlace=HAVA-sky" \
              f"&outboundDate={outbound_date}" \
              "&adults=1"
    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': "1f56c1c2famsh6ad3494bc0b9eb3p13f3a4jsn668d79c5fd77",
        'content-type': "application/x-www-form-urlencoded"
    }

    response = requests.request("POST", url, data=payload, headers=headers)
    while response.text != '{}':
        response = requests.request("POST", url, data=payload, headers=headers)
        time.sleep(1)

    location = response.headers['Location'].split('/')[-1]
    return location


def poll_results(key):
    url = f"https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/uk2/v1.0/{key}"

    querystring = {
        "pageIndex": "0",
        "pageSize": "1000",
        "stops": "0"
    }

    headers = {
        'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
        'x-rapidapi-key': "1f56c1c2famsh6ad3494bc0b9eb3p13f3a4jsn668d79c5fd77"
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


def main():
    best = None
    current = datetime.date(2020, 4, 1)
    end = datetime.date(2020, 5, 14)
    while current < end:
        for i in range(17, 23):
            key = create_session(str(current), current + datetime.timedelta(days=i))
            flight = poll_results(key)
            message = ' '.join(map(str, (current, i, *flight)))
            if flight[0] < 600:
                message = '\033[92m' + message + '\033[0m'
            print(message)
            if not best or flight[0] < best[2]:
                best = (current, i, *flight)
        current += datetime.timedelta(days=1)

    print('=============================')
    print(best)
    print('=============================')


if __name__ == '__main__':
    main()
