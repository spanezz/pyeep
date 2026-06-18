import {Message} from "messages";

export class Hub
{
    constructor(url)
    {
        this.url = url;
        this.ws = new WebSocket(url);
        this.ws.addEventListener("open", this.on_open);
        this.ws.addEventListener("close", this.on_close);
        this.ws.addEventListener("message", this.on_message);
        this.ws.addEventListener("error", this.on_error);

        this.components = {}
    }

    on_open(evt) 
    {
        console.log(this.url, "websocket connected");
    }
    on_message(evt) 
    {
        console.log(this.url, "websocket message", evt);
        let msgdata;
        try {
            msgdata = JSON.parse(evt.data);
        } catch (e) {
            console.error("Failed to decode json %o: %o", evt.data, e)
            return;
        }

        let msg;
        try {
            msg = Message.load(msgdata.msg);
        } catch (e) {
            console.error("Failed to load message %o: %o", msgdata, e)
            return
        }

        console.log("PARSED FOR", msgdata.dst, "MSG", msg);

        let component = this.components[msgdata.dst];
        if (component !== undefined)
            component.receive(msg)
    }
    on_close(evt) 
    {
        console.error(this.url, "websocket closed", evt);
    }

    on_error(evt) 
    {
        console.error(this.url, "websocket error", evt);
    }

    add_component(component)
    {
        this.components[component.routing_key] = component
    }
}

export class Component
{
    constructor(hub, name, routing_key)
    {
        this.hub = hub
        this.name = name
        this.routing_key = routing_key

        this.hub.add_component(this)
    }

    receive(msg)
    {
        console.log(this.routing.key, "RECEIVED", msg)
    }
}
