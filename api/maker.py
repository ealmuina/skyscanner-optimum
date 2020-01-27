import sys
import time

from .base import *


class Maker(BaseWorker):
    def __init__(self, config):
        super().__init__(config)

        # Setup rabbitmq
        self.channel.queue_bind(
            exchange=self.exchange,
            queue=self.queue,
            routing_key='make'
        )
        self.channel.basic_consume(
            queue=self.queue,
            on_message_callback=self._create_session
        )

    def _create_session(self, ch, method, props, body):
        url = "https://skyscanner-skyscanner-flight-search-v1.p.rapidapi.com/apiservices/pricing/v1.0"
        query = json.loads(body)
        payload = "cabinClass=economy" \
                  "&country=ES" \
                  "&currency=EUR" \
                  "&locale=es-ES" \
                  f"&originPlace={query['origin']}" \
                  f"&destinationPlace={query['destination']}" \
                  f"&outboundDate={query['start_date']}" \
                  "&adults=1"
        if 'end_date' in query:
            payload += f"&inboundDate={query['end_date']}"

        headers = {
            'x-rapidapi-host': "skyscanner-skyscanner-flight-search-v1.p.rapidapi.com",
            'x-rapidapi-key': query['api_key'],
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
                        attempts = 0
            finally:
                time.sleep(API_WAIT_TIME)

        location = response.headers['Location'].split('/')[-1]
        self._send_message(
            json.dumps({
                'location': location,
                'query': query
            }),
            props.correlation_id,
            props.reply_to
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

        logger.info(f'Created session with api-key {query["api_key"]}')

    def _send_message(self, message, correlation_id, reply_to):
        self.channel.basic_publish(
            exchange=self.exchange,
            routing_key='poll',
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                reply_to=reply_to,
                content_type='application/json'
            ),
            body=message
        )

    def run(self):
        self.channel.start_consuming()


if __name__ == '__main__':
    with open(sys.argv[1]) as file:
        config = json.load(file)
        maker = Maker(config)
        maker.run()
