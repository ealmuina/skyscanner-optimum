import datetime
import json
import uuid

import pika

from .base import BaseWorker, logger


class FlightQuery(BaseWorker):
    def __init__(self, config, query, callback):
        super().__init__(config)

        self.uuid = str(uuid.uuid4())
        self.api_keys = config['x-rapidapi-keys']
        self.callback = callback

        self.pending_sessions = 0  # stores the number of sessions pending from response
        self.results = []

        # Common data to round and one-way trips
        self.origin = query['origin']
        self.destination = query['destination']
        self.start_date = query['start_date']
        self.end_date = query['end_date']

        # Data exclusive to round trips
        self.min_days = query.get('min_days', None)
        self.max_days = query.get('max_days', None)

        # Setup rabbitmq
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.queue = result.method.queue
        self.channel.basic_consume(
            queue=self.queue,
            on_message_callback=self._result_callback
        )

    def _send_message(self, obj):
        self.channel.basic_publish(
            exchange='',
            routing_key='skyscanner-make',
            properties=pika.BasicProperties(
                correlation_id=self.uuid,
                reply_to=self.queue,
                content_type='application/json'
            ),
            body=json.dumps(obj)
        )

    def _result_callback(self, ch, method, props, body):
        if self.uuid == props.correlation_id:
            self.results.append(json.loads(body))
            self.pending_sessions -= 1

        directs, with_stops = [], []
        if self.pending_sessions == 0:
            for r in self.results:
                query = r['query']
                if r['direct']:
                    price, airlines = r['direct']
                    directs.append(Result(
                        price=price,
                        airlines=airlines,
                        origin=query['origin'],
                        destination=query['destination'],
                        start_date=query['start_date'],
                        end_date=query.get('end_date', None)
                    ))
                if r['with_stops']:
                    price, airlines = r['with_stops']
                    with_stops.append(Result(
                        price=price,
                        airlines=airlines,
                        origin=query['origin'],
                        destination=query['destination'],
                        start_date=query['start_date'],
                        end_date=query.get('end_date', None)
                    ))

            directs.sort()
            with_stops.sort()
            self.callback(directs, with_stops)
            self.connection.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    def execute(self):
        current = self.start_date

        while current <= self.end_date:
            message = {
                'api_key': self.api_keys[self.pending_sessions % len(self.api_keys)],
                'start_date': str(current),
                'origin': self.origin,
                'destination': self.destination
            }
            if self.min_days:
                for i in range(self.min_days, self.max_days + 1):
                    message.update({
                        'api_key': self.api_keys[self.pending_sessions % len(self.api_keys)],
                        'end_date': str(current + datetime.timedelta(days=i))
                    })
                    logger.info(f"{current} {i}")
                    self._send_message(message)
                    self.pending_sessions += 1
            else:
                self._send_message(message)
                self.pending_sessions += 1

            current += datetime.timedelta(days=1)

        while self.pending_sessions:
            self.connection.process_data_events()


class Result:
    def __init__(self, price, airlines, origin, destination, start_date, end_date=None):
        self.price = price
        self.airlines = airlines
        self.origin = origin
        self.destination = destination
        self.start_date = start_date
        self.end_date = end_date

    def __lt__(self, other):
        return self.price < other.price

    def __str__(self):
        start_date = datetime.datetime.strptime(self.start_date, '%Y-%m-%d')
        result = f'{datetime.datetime.strftime(start_date, "%d/%m/%Y")}: '
        if self.end_date:
            end_date = datetime.datetime.strptime(self.end_date, '%Y-%m-%d')
            days = (end_date - start_date).days
            result += f'{days} days '
        result += f'for {"%.2f" % self.price}€ on {"-".join(self.airlines)}'
        return result
