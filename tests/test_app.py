from __future__ import annotations

import unittest
from unittest import mock

import pyeep.app


class MockNamespace:
    debug = False
    verbose = False


class TestApp(unittest.TestCase):
    def test_app(self):
        app = pyeep.app.App(args=MockNamespace())
        with app:
            with mock.patch("pyeep.app.Queue.get", side_effect=KeyboardInterrupt):
                app.main()
