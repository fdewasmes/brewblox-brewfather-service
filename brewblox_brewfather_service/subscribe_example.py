"""
Example on how to listen to MQTT events.

For an example on how to publish events, see publish_example.py
"""


from aiohttp import web
from brewblox_service import brewblox_logger, features, mqtt

LOGGER = brewblox_logger(__name__)


class SubscribingFeature(features.ServiceFeature):

    async def startup(self, app: web.Application):
        """Add event handling

        To get messages, you need to call `mqtt.subscribe(topic)` and `mqtt.listen(topic, callback)`.

        You can set multiple listeners for each call to subscribe, and use wildcards to filter messages.

        Wildcards are + or #

        + matches a single level.

        "controller/+/sensor" subscriptions will receive (example) topics:
        - controller/block/sensor
        - controller/container/sensor

        But not:
        - controller
        - controller/nested/block/sensor
        - controller/block/sensor/nested

        # is a greedier wildcard: it will match as few or as many values as it can
        Plain # subscriptions will receive all messages published to the eventbus.

        A subscription of "controller/#" will receive:
        - controller
        - controller/block/sensor
        - controller/container/nested/sensor

        For more information on this, see
        http://www.steves-internet-guide.com/understanding-mqtt-topics/
        """
        await mqtt.listen(app, 'brewcast/history/#', self.on_message)
        await mqtt.subscribe(app, 'brewcast/history/#')

    async def shutdown(self, app: web.Application):
        """Shutdown and remove event handlers

        unsubscribe() and unlisten() must be called
        with the same arguments as subscribe() and listen()
        """
        await mqtt.unsubscribe(app, 'brewcast/history/#')
        await mqtt.unlisten(app, 'brewcast/history/#', self.on_message)

    async def on_message(self, topic: str, message: dict):
        """Example message handler for MQTT events.

        Services can choose to publish / subscribe events to communicate between them.
        These events are for loose communication: you broadcast something,
        and don't really care by whom it gets picked up.

        When subscribing to an event, you provide a callback (example: this function)
        that will be called every time a relevant event is published.

        Args:
            topic (str):
                The topic to which this event was published.
                This will always be specific - no wildcards.

            message (dict):
                The content of the event.
                Messages handled by mqtt.py are always parsed to JSON.

        """
        LOGGER.info(f'Message on topic {topic} = {message}')


def setup(app: web.Application):
    # We register our feature here
    # It will now be automatically started when the service starts
    features.add(app, SubscribingFeature(app))


def fget(app: web.Application) -> SubscribingFeature:
    # Retrieve the registered instance of SubscribingFeature
    return features.get(app, SubscribingFeature)
