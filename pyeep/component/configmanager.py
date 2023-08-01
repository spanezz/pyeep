from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..app.hub import HubConfig
from ..component.aio import AIOComponent
from ..messages import Configure, NewComponent, Shutdown


class ConfigManager(AIOComponent):
    """
    Input that can be connected/disconnected
    """
    def __init__(self, config_file: Path = Path(".pyeep.config"), **kwargs):
        super().__init__(**kwargs)
        self.config_file = config_file

        self.components: dict[str, dict[str, Any]]
        try:
            with self.config_file.open("rt") as fd:
                config = yaml.load(fd, Loader=yaml.SafeLoader)
            if (components := config.get("components")):
                self.components = components
            else:
                self.components = {}
        except FileNotFoundError:
            self.components = {}

    async def run(self):
        while True:
            match (msg := await self.next_message()):
                case Shutdown():
                    break
                case NewComponent():
                    if (config := self.components.get(msg.src.name)):
                        self.send(Configure(dst=msg.src.name, config=config))
                case HubConfig():
                    self.components |= msg.components

                    # Save
                    with self.config_file.open("wt") as fd:
                        yaml.dump({"components": self.components}, stream=fd)
