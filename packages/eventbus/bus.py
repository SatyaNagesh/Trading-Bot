"""RabbitMQ Event Bus — publisher and consumer."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType, RobustConnection

from packages.core.config import settings
from packages.core.exceptions import QuantLabError
from packages.core.logging import get_logger

logger = get_logger("event_bus")

EXCHANGE = "quantlab.events"
QUEUE_PREFIX = "quantlab"


class EventBusError(QuantLabError):
    pass


@dataclass
class EventBus:
    connection: RobustConnection | None = None
    channel: aio_pika.RobustChannel | None = None
    exchange: aio_pika.RobustExchange | None = None

    async def connect(self) -> None:
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_dsn)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            EXCHANGE, ExchangeType.TOPIC, durable=True,
        )
        logger.info("eventbus_connected", exchange=EXCHANGE)

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()

    async def publish(
        self,
        routing_key: str,
        payload: dict,
        source: str = "unknown",
    ) -> None:
        if not self.exchange:
            await self.connect()
        envelope = {
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": routing_key,
            "payload": payload,
        }
        message = Message(
            body=json.dumps(envelope).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self.exchange.publish(message, routing_key=routing_key)
        logger.debug("event_published", routing_key=routing_key)

    async def subscribe(
        self,
        routing_key: str,
        queue_name: str | None = None,
    ) -> aio_pika.RobustQueue:
        if not self.channel:
            await self.connect()
        q = await self.channel.declare_queue(
            queue_name or f"{QUEUE_PREFIX}.{routing_key.replace('.', '_')}",
            durable=True,
        )
        await q.bind(self.exchange, routing_key=routing_key)
        return q

    async def consume(
        self,
        routing_key: str,
        callback,
        queue_name: str | None = None,
    ) -> None:
        q = await self.subscribe(routing_key, queue_name)
        async for message in q:
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                    await callback(data)
                except Exception as e:
                    logger.error("event_processing_failed", error=str(e), routing_key=routing_key)


async def emit_event(event_type: str, payload: dict, source: str = "unknown") -> None:
    bus = EventBus()
    await bus.publish(event_type, payload, source=source)
    await bus.close()
