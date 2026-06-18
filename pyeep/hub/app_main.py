from collections import defaultdict
from typing import TYPE_CHECKING, Any

import aiohttp_jinja2
import jinja2
from aiohttp import web

from pyeep.nodes.web import WebComponent
from pyeep.utils.modules import get_package_path

if TYPE_CHECKING:
    from .hub import HubApp


class Home(web.View):
    @aiohttp_jinja2.template("home.html")
    async def get(self) -> dict[str, Any]:
        from pyeep.hub.hub import Scenes

        scenes = self.request.app["scenes"]
        assert isinstance(scenes, Scenes)
        return {"scenes": scenes.scenes}


class Main:
    def __init__(self, *, hub: "HubApp") -> None:
        self.hub = hub

    def static_url(self, path: str) -> str:
        """Return a static URL for a relative path."""
        return "/static/" + path.lstrip("/")

    @jinja2.pass_context
    def scene_static_url(
        self, context: jinja2.runtime.Context, path: str
    ) -> str:
        """Return a static URL for a scene-relative path."""
        from pyeep.scenes.base import WebScene

        if (scene := context.get("scene")) is None:
            raise jinja2.TemplateError(
                "scene_static_url used without a scene in context"
            )
        assert isinstance(scene, WebScene)
        return "/static/scenes/{scene.name}" + path.lstrip("/")

    def make_app(self) -> web.Application:
        """Make the main hub application."""
        app = web.Application()
        app["scenes"] = self.hub.scenes
        app.router.add_view("/", Home)

        # Examples of how to add assets from system dirs
        # app.router.add_static(
        #     "/static/bootstrap5", "/usr/share/bootstrap-html"
        # )

        # Add web components
        component_loaders: dict[str, dict[str, jinja2.BaseLoader]] = (
            defaultdict(dict)
        )
        for wc in self.hub.components.values():
            if not isinstance(wc, WebComponent):
                continue

            # Static router
            if static_path := wc.get_static_path():
                app.router.add_static(
                    f"/static/{wc.section}/{wc.name}", static_path
                )

            # Template loader
            if template_path := wc.get_template_path():
                component_loaders[wc.section][wc.name] = (
                    jinja2.FileSystemLoader(template_path)
                )
            else:
                tpl_name = f"{wc.section}_ui.html"
                component_loaders[wc.section][wc.name] = jinja2.DictLoader(
                    {"ui.html": f"{{% extends '{tpl_name}' %}}"}
                )

            # Views
            wc.add_views(app, prefix=f"{wc.section}/{wc.name}")

        # Add static router for the main hub
        app.router.add_static(
            "/static", get_package_path("pyeep.hub") / "static"
        )

        aiohttp_jinja2.setup(
            app,
            context_processors=[aiohttp_jinja2.request_processor],
            loader=jinja2.ChoiceLoader(
                [
                    jinja2.PackageLoader("pyeep.hub"),
                    jinja2.PrefixLoader(
                        {
                            section: jinja2.PrefixLoader(loaders)
                            for section, loaders in component_loaders.items()
                        }
                    ),
                ]
            ),
            enable_async=True,
        )

        j2_env = aiohttp_jinja2.get_env(app)
        j2_env.globals.update(
            static_url=self.static_url,
            scene_static_url=self.scene_static_url,
            ws_url=f"ws://{self.hub.args.host}:{self.hub.args.port}/pyeep/ui/io/",
        )

        return app
