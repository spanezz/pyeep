from typing import TYPE_CHECKING

import jinja2
import aiohttp_jinja2
from aiohttp import web

from pyeep.utils.modules import get_package_path

if TYPE_CHECKING:
    from .hub import Hub


class Home(web.View):
    @aiohttp_jinja2.template("home.html")
    async def get(self):
        from pyeep.hub.hub import Scenes

        scenes = self.request.app["scenes"]
        assert isinstance(scenes, Scenes)
        return {"scenes": scenes.scenes}


class Main:
    def __init__(self, *, hub: "Hub") -> None:
        self.hub = hub
        self.app = self.make_app()

    def static_url(self, path: str) -> str:
        """Return a static URL for a relative path."""
        return "/static/" + path.lstrip("/")

    @jinja2.pass_context
    def scene_static_url(
        self, context: jinja2.runtime.Context, path: str
    ) -> str:
        """Return a static URL for a scene-relative path."""
        from pyeep.scenes.base import Scene

        if (scene := context.get("scene")) is None:
            raise jinja2.TemplateError(
                "scene_static_url used without a scene in context"
            )
        assert isinstance(scene, Scene)
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

        # Add individual scenes
        scene_loaders: dict[str, jinja2.PackageLoader] = {}
        for scene in self.hub.scenes.scenes.values():
            # Static router
            app.router.add_static(
                f"/static/scenes/{scene.name}",
                get_package_path(scene.desc.module) / "static",
            )
            # Template loader
            scene_loaders[scene.name] = jinja2.PackageLoader(scene.desc.module)
            # Views
            prefix = f"scenes/{scene.name}"
            scene.add_views(app, prefix=prefix)

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
                        {"scenes": jinja2.PrefixLoader(scene_loaders)}
                    ),
                ]
            ),
        )

        j2_env = aiohttp_jinja2.get_env(app)
        j2_env.globals.update(
            static_url=self.static_url,
            scene_static_url=self.scene_static_url,
        )

        return app
