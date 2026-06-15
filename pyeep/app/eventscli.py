import cmd
from typing import override

from pyeep.app.client import ClientApp
from pyeep.app.sync import SyncClientApp
from pyeep.models.messages.power import SetGroupPower, IncreaseGroupPower


class EventsCli(SyncClientApp, cmd.Cmd):
    """Interacively send pyeep messages."""

    def __init__(self) -> None:
        SyncClientApp.__init__(
            self, app=ClientApp(name="eventscli", handle_sigterm_sigint=False)
        )
        cmd.Cmd.__init__(self)

    @override
    def main(self) -> None:
        self.cmdloop()

    def do_quit(self, arg: str) -> bool:
        return True

    def do_EOF(self, arg: str) -> bool:
        return True

    def do_power(self, arg: str) -> None:
        args = arg.split()
        group = int(args[0])
        if (value := args[1]).startswith("+"):
            self.send(IncreaseGroupPower(group=group, amount=int(value[1:])))
        else:
            self.send(SetGroupPower(group=group, power=int(value)))


def main() -> None:
    eventscli = EventsCli()
    eventscli.run()


if __name__ == "__main__":
    main()
