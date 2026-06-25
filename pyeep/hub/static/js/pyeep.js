import {Message} from "messages";

Handlebars.registerHelper("tofixed", (num, digits) => {
    console.log("HANDLEBAR TOFIXED", num, digits);
    return num.toFixed(digits);
});

export class Hub
{
    constructor(url)
    {
        this.url = url;
        this.components = {}
        this.ws = new WebSocket(url);
        this.ws.addEventListener("open", evt => this.on_open(evt));
        this.ws.addEventListener("close", evt => this.on_close(evt));
        this.ws.addEventListener("message", evt => this.on_message(evt));
        this.ws.addEventListener("error", evt => this.on_error(evt));
        this.el_disconnected = document.getElementById("server-disconnected");
    }

    on_open(evt) 
    {
        console.log(this.url, "websocket connected");
        for (let component of Object.values(this.components))
            component.send({"action": "connected"})
    }
    on_message(evt) 
    {
        let msgdata;
        try {
            msgdata = JSON.parse(evt.data);
        } catch (e) {
            console.error("Failed to decode json %o: %o", evt.data, e)
            return;
        }
        // console.log(this.url, "websocket message payload", msgdata);

        let component = this.components[msgdata.rk];
        if (component !== undefined)
            component.receive(msgdata.msg)

        /*
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
        */
    }
    on_close(evt) 
    {
        console.error(this.url, "websocket closed", evt);
        this.el_disconnected.style.display = "flex";
    }

    on_error(evt) 
    {
        console.error(this.url, "websocket error", evt);
    }

    add_component(component)
    {
        this.components[component.routing_key] = component
        console.log("Component %o added", component);
        if (this.ws.readyState == WebSocket.OPEN)
            component.send({"action": "connected"})
    }
}

export class Component
{
    constructor(el)
    {
        this.el = el;
        this.hub = window.pyeep.hub;
        this.name = el.dataset["pyeep_name"];
        this.routing_key = el.dataset["pyeep_routing_key"];

        this.hub.add_component(this)

        // Load templates
        this.templates = {};
        for (let script of this.el.getElementsByTagName("script"))
        {
            if (script.attributes.type.value != "text/html")
                continue;
            const name = script.attributes.name.value;
            if (name === undefined)
            {
                console.warning("Found template without name: %o", script);
                continue;
            }
            this.templates[name] = Handlebars.compile(script.innerText);
        }
    }

    // Send a message to the Hub side of the component
    send(msg)
    {
        this.hub.ws.send(JSON.stringify({"rk":this.routing_key, "msg": msg}));
    }

    // Recevie a message from the Hub side of the component
    receive(msg)
    {
    }
}

export class Group extends Component
{
    constructor(el)
    {
        super(el);
        this.el_members = el.getElementsByClassName("members")[0];
        this.el_color = document.getElementById(`${this.el.id}-color`);
        this.el_power = document.getElementById(`${this.el.id}-power`);
    }

    receive(msg)
    {
        const members = msg.membership
        if (members !== undefined)
        {
            // Update members list
            this.el_members.innerHTML = this.templates.members({members: members});
        }
        const color = msg.color;
        if (color !== undefined)
        {
            this.el_color.setAttribute("fill", color);
        }
        const power = msg.power;
        if (power !== undefined)
        {
            this.el_power.setAttribute("width", `${power * 100}%`);
        }
    }
}

export class Scene extends Component
{
    constructor(el)
    {
        super(el);
        this.el_playpause = document.getElementById(`${this.el.id}-playpause`);
        this.el_playpause.addEventListener("click", evt => { this.on_play_pause(evt); });
    }

    on_play_pause(evt)
    {
        this.send({"action": "toggle-active"});
    }

    receive(msg)
    {
        const active = msg.active;
        if (active !== undefined)
        {
            if (active)
                this.el_playpause.innerText = "⏸";
            else
                this.el_playpause.innerText = "⏵";
        }
        super.receive(msg);
    }
}
