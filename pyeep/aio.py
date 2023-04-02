from __future__ import annotations

import argparse
import asyncio

from .app import App, Component, Thread


class AIOComponent(Component):
    async def run(self):
        pass


class AIOThread(Thread):
    def __init__(self):
        super().__init__(name="aio")
        self.loop: asyncio.AbstractEventLoop | None = None

    def run(self):
        asyncio.run(self.aio_main())

    async def aio_main(self):
        self.loop = asyncio.get_event_loop()
        await asyncio.gather(
            *(c.run() for c in self.components.values())
        )

    def add_component(self, component: Component) -> bool:
        if isinstance(component, AIOComponent):
            self.components[component.name] = component
            return True

        return super().add_component(component)


class AIOApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_thread(AIOThread())
