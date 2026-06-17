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
        let msg = Message.load(JSON.parse(evt.data));
        console.log("PARSED AS", msg);
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
}
