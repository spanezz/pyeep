import {Scene} from "pyeep";

export class Pianotrainer extends Scene
{
    constructor(el)
    {
        super(el);
        this.el_game = el.getElementsByClassName("game")[0];
    }

    receive(msg)
    {
        if (msg.game !== undefined)
            this.el_game.innerHTML = this.templates.game(msg.game);
        super.receive(msg);
    }
}

