import json
import logging

import pika
import requests

API_WAIT_TIME = 1
API_MAX_ERRORS = 50
API_REFRESH_TIME = 1.5 * 60

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


class BaseWorker:
    def __init__(self, config):
        self.config = config

        # Setup rabbitmq
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=config['rabbitmq-host'],
            credentials=pika.PlainCredentials(config['rabbitmq-user'], config['rabbitmq-password'])
        ))
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=1)


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
