#
# journal/router.py
#
# futaba - A Discord Mod bot for the Programming server
# Copyright (c) 2017-2018 Jake Richardson, Ammon Smith, jackylam5
#
# futaba is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import asyncio
import logging
from collections import defaultdict
from itertools import chain
from pathlib import PurePath

from .process import process_content

logger = logging.getLogger(__name__)

__all__ = ["Router"]


def attrs_match(obj, attrs):
    for attr, value in attrs.items():
        if not hasattr(obj, attr) or getattr(obj, attr) != value:
            return False
    return True


class Router:
    __slots__ = ("paths", "queue")

    def __init__(self):
        self.paths = defaultdict(list)
        self.queue = asyncio.Queue()

    def start(self, eventloop):
        logger.info("Start journal event processing task")
        eventloop.create_task(self.handle_events())

    def get(self, path, **attrs):
        logger.debug(
            "Getting first listener on path '%s' that matches attributes: %r",
            path,
            attrs,
        )

        path = PurePath(path)
        for listener in self.paths[path]:
            if attrs_match(listener, attrs):
                return listener
        return None

    def register(self, listener):
        logger.info("Registering %r on '%s'", listener, listener.path)
        self.paths[listener.path].append(listener)

    def unregister(self, listener):
        logger.info("Unregistering %r from '%s'", listener, listener.path)
        self.paths[listener.path].remove(listener)

    async def handle_events(self):
        events = []

        while True:
            logger.debug("Waiting for new journal event")
            event_path, guild, content, attributes = await self.queue.get()
            logger.debug("Got journal event on %s: '%s'", event_path, content)
            content = process_content(content, attributes)
            logger.debug("Journal content after processing: '%s'", content)

            # Add events for this path
            for path in chain((event_path,), event_path.parents):
                for listener in self.paths[path]:
                    if listener.check(path, guild, content, attributes):
                        events.append(
                            listener.handle(event_path, guild, content, attributes)
                        )

            # Run all the event handlers
            try:
                await asyncio.gather(*events)
            except Exception as error:
                logger.error("Error while running journal handlers", exc_info=error)

            events.clear()
