from typing import override

import rich

from pyeep.app.client import ClientApp
from pyeep.component.component import Component
from pyeep.models.messages import Message


class DumpMessages(Component):
    def __init__(self) -> None:
        super().__init__(name="dumpmessages")
        self.console = rich.get_console()

    @override
    async def receive(self, msg: Message) -> None:
        self.console.print("Received:", str(msg), highlight=False)


class Inspector(ClientApp):
    """Inspect the pyeep system."""

    def __init__(self) -> None:
        super().__init__(name="inspector")
        self.webclient.add_component(DumpMessages())


if __name__ == "__main__":
    Inspector.run()
