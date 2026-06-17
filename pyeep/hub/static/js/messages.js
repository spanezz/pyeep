let registry = {}
function register(msgclass, primitive) {
    msgclass.primitive = primitive;
    registry[primitive] = msgclass;
}

export class Message
{
    constructor(msgdata)
    {
        this.ts = msgdata.ts;
        this.src = msgdata.src;
    }

    static load(msgdata)
    {
        if (msgdata.primitive === undefined)
            console.error("Primitive is undefined in message", msgdata);
        let message_class = registry[msgdata.primitive];
        if (message_class === undefined)
            console.error("Unknown primitive", msgdata.primitive, "for", msgdata);
        return new message_class(msgdata);
    }
}
register(Message, "pyeep.models.messages.messages.Message");

export class Event extends Message
{
}
register(Event, "pyeep.models.messages.messages.Event");

export class Broadcast extends Message
{
}
register(Broadcast, "pyeep.models.messages.messages.Broadcast");

export class Command extends Message
{
    constructor(msgdata)
    {
        super(msgdata);
        this.dst = msgdata.dst;
    }
}
register(Command, "pyeep.models.messages.messages.Command");

export class Shutdown extends Broadcast
{
}
register(Shutdown, "pyeep.nodes.messages.Shutdown");

export class HubConnected extends Broadcast
{
}
register(HubConnected, "pyeep.nodes.messages.HubConnected");

export class ComponentAdded extends Event
{
}
register(ComponentAdded, "pyeep.nodes.messages.ComponentAdded");

export class ComponentRemoved extends Event
{
}
register(ComponentRemoved, "pyeep.nodes.messages.ComponentRemoved");

