from typing import override, Unpack

import rich

from pyeep.app.base import BaseAppArgs
from pyeep.app.client import ClientApp
from pyeep.models.messages import Command


class Inspector(ClientApp):
    """Inspect the pyeep system."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.console = rich.get_console()

    @override
    async def receive_command(self, cmd: Command) -> None:
        self.console.print("Received:", str(cmd), highlight=False)


if __name__ == "__main__":
    Inspector.run()
