"""Expose browser coverage as an explicit pytest selection."""

import pytest


BROWSER_CLASSES = {
    "BrowserTests", "PluginBrowserTests", "MoveBoxRegressionTests",
    "RealRequestTests", "ServeBrowserTests", "URLBrowserTests",
    "URLPluginBrowserTests", "LoopBrowserTests",
}


def pytest_collection_modifyitems(items):
    for item in items:
        if ((item.cls and item.cls.__name__ in BROWSER_CLASSES) or
                item.name == "test_real_mobile_png_width_390"):
            item.add_marker(pytest.mark.browser)
