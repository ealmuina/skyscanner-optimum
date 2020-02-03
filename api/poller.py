import sys

from .base import *

POLLER_WAIT_TIME = 5


class Poller(BaseWorker):
    def __init__(self, config):
        super().__init__(config)

        # Setup rabbitmq
        result = self.channel.queue_declare(queue='skyscanner-poll', auto_delete=True)
        self.queue = result.method.queue
        self.channel.basic_consume(
            queue=self.queue,
            on_message_callback=self._poll_session
        )

    @staticmethod
    def _get_best_flight(itineraries, flights):
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
                        tuple(airlines)
                    )

        return best

    def _poll_session(self, ch, method, props, body):
        data = json.loads(body)
        url = f"https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/uk2/v1.0/{data['location']}"
        headers = {
            'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
            'x-rapidapi-key': data['query']['api_key']
        }

        querystring = {"pageIndex": "0", "pageSize": "100", "stops": "1", "sortType": "duration"}

        response = {}
        attempts = 0
        while 'Status' not in response or response['Status'] != 'UpdatesComplete':
            self.connection.sleep(POLLER_WAIT_TIME)
            try:
                response = requests.request("GET", url, headers=headers, params=querystring)
            except Exception:
                continue
            response = json.loads(response.text)
            attempts += 1
            if attempts > API_MAX_ERRORS:
                logger.warning("Too many errors received. I'm going to sleep for a while.")
                self.connection.sleep(API_REFRESH_TIME)
                attempts = 0

        itineraries = response['Itineraries']
        legs = response['Legs']
        carriers = response['Carriers']

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

        best_direct = self._get_best_flight(itineraries, direct_flights)
        best_with_stops = self._get_best_flight(itineraries, stops_flights)

        self._send_message(
            json.dumps({
                'direct': best_direct,
                'with_stops': best_with_stops,
                'query': data['query']
            }),
            props.correlation_id,
            props.reply_to
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

        logger.info(f'Polled session with api-key {data["query"]["api_key"]}')

    def _send_message(self, message, correlation_id, destination):
        self.channel.basic_publish(
            exchange='',
            routing_key=destination,
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                content_type='application/json'
            ),
            body=message
        )

    def run(self):
        self.channel.start_consuming()


if __name__ == '__main__':
    with open(sys.argv[1]) as file:
        config = json.load(file)
        poller = Poller(config)
        poller.run()
