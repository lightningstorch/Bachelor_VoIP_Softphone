import asyncio
import threading
from typing import Tuple, Any, Coroutine, Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel, AbstractRobustExchange, AbstractRobustQueue
from aio_pika.exchange import ExchangeType, Exchange

from config.config import rabbitmq_host, rabbitmq_password, rabbitmq_user, rabbitmq_port

# TODO Integrate the logging
# TODO Advanced Exception handling
# TODO Restructuring


class AsyncMessageService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        # ensure that initialization only happens once
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.thread.start()

        self.connection = asyncio.run_coroutine_threadsafe(
            self._init_connection(),
            self.loop
        ).result()

        self._subscribers: dict[str, Tuple[AbstractRobustQueue, AbstractRobustChannel, str]] = {}
        self._publishers: dict[str, Tuple[AbstractRobustChannel, AbstractRobustExchange]] = {}

        self.is_closed = False


    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance


    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


    async def _init_connection(self) -> AbstractRobustConnection:
        return await aio_pika.connect_robust(
            host=rabbitmq_host,
            port=rabbitmq_port,
            login=rabbitmq_user,
            password=rabbitmq_password,
            loop=self.loop
        )


    def publish(self, message, exchange_name: str, exchange_type: ExchangeType, routing_key: str = ""):
        asyncio.run_coroutine_threadsafe(
            self.publish_async(message, exchange_name, exchange_type, routing_key),
            self.loop
        )


    async def publish_async(self, message, exchange_name: str, exchange_type: ExchangeType, routing_key: str):
        channel_exchange = self._publishers.get(exchange_name)

        if channel_exchange is None:
            channel = await self.connection.channel(publisher_confirms=True)
            # declare the exchange
            exchange = await channel.declare_exchange(
                exchange_name,
                exchange_type,
                durable=True,
                auto_delete=False,
            )
            # save from a channel and exchange for cpu load reduction
            self._publishers[exchange_name] = (channel, exchange)
        else:
            channel, exchange = channel_exchange


        # publish the message in the channel
        await exchange.publish(
            aio_pika.Message(message.encode()),
            routing_key=routing_key,
        )


    def subscribe(self, callback: callable, exchange_name: str, exchange_type: str, queue_name: str, routing_key: str = ""):
        return asyncio.run_coroutine_threadsafe(
            self.subscribe_async(callback, exchange_name, exchange_type, queue_name, routing_key),
            self.loop
        )


    async def subscribe_async(self, callback: callable, exchange_name: str, exchange_type: str, queue_name: str, routing_key: str):
        channel = await self.connection.channel()

        # Default prefetch_count is 1; if you see “Got frame for closed channel” errors again,
        # try increasing prefetch_count (e.g., to 5) to allow multiple unacknowledged messages.
        await channel.set_qos(prefetch_count=1)

        await channel.declare_exchange(exchange_name, exchange_type, durable=True)
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange_name, routing_key=routing_key)

        consumer_tag = await queue.consume(callback)

        #save the channel and consumer_tag for closing the channel
        self._subscribers[queue_name] = (queue, channel, consumer_tag)


    def unsubscribe(self, queue_name: str):
        asyncio.run_coroutine_threadsafe(self.unsubscribe_async(queue_name), self.loop)


    async def unsubscribe_async(self, queue_name: str):
        entry = self._subscribers.get(queue_name)
        if not entry:
            return

        queue, channel, consumer_tag = entry

        try:
            await queue.cancel(consumer_tag)
        except Exception as e:
            print(f"Error while unsubscribing from queue {queue_name}: {e}")

        await asyncio.sleep(0.1)

        try:
            await channel.close()
        except Exception as e:
            print(f"Error while closing channel for queue {queue_name}: {e}")


    def close(self):
        asyncio.run_coroutine_threadsafe(self.close_async(), self.loop).result()


    async def close_async(self):
        self.is_closed = True
        # close all channels for consumer
        for queue_name in list(self._subscribers):
            await self.unsubscribe_async(queue_name)

        # close all channels for publisher
        for channel, _ in list(self._publishers.values()):
            try:
                await channel.close()
            except Exception as e:
                print(f"Error while closing publisher channel: {e}")

        # close the connection
        await self.connection.close()




def get_message_service() -> AsyncMessageService:
    return AsyncMessageService()


