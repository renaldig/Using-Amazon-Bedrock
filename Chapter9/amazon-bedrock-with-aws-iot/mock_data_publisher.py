import time
import json
import random
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# AWS IoT endpoint, replace with your own
ENDPOINT = "your-endpoint.amazonaws.com"
CLIENT_ID = "EnvironmentSensor"
PATH_TO_CERT = "certs/certificate.pem.crt"
PATH_TO_KEY = "certs/private.pem.key"
PATH_TO_ROOT = "certs/AmazonRootCA1.pem"
TOPIC = "environment/data"

# Initialize MQTT Client
mqtt_client = AWSIoTMQTTClient(CLIENT_ID)
mqtt_client.configureEndpoint(ENDPOINT, 8883)
mqtt_client.configureCredentials(PATH_TO_ROOT, PATH_TO_KEY, PATH_TO_CERT)

mqtt_client.connect()
print('Connected to AWS IoT Core')

while True:
    temperature = round(random.uniform(20.0, 30.0), 2)
    humidity = round(random.uniform(30.0, 70.0), 2)
    co2 = round(random.uniform(400.0, 800.0), 2)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

    data = {
        'Timestamp': timestamp,
        'Temperature': temperature,
        'Humidity': humidity,
        'CO2': co2
    }

    message = json.dumps(data)
    mqtt_client.publish(TOPIC, message, 1)
    print(f'Published: {message} to the topic: {TOPIC}')
    time.sleep(5)
