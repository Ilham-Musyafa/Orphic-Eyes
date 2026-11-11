"""allow_local comes only from user config; metadata/link-local IPs are always blocked."""

import importlib
import json
import os
import socket
import tempfile
import unittest
from unittest.mock import patch

import orphic_tools as tools
from engine import _url_network as network

url_capture = importlib.import_module("engine.url_capture")


class AllowLocalConfigTests(unittest.TestCase):
    def test_allow_local_absent_from_every_tool_schema(self):
        for name, schema, _ in tools.TOOL_DEFINITIONS:
            self.assertNotIn("allow_local", schema["parameters"]["properties"], name)

    def test_model_supplied_allow_local_is_rejected(self):
        with patch.object(tools, "plugin_config", return_value={"allow_local": True}):
            for handler, args in ((tools.handle_compare, {"before_url": "http://127.0.0.1/",
                                                          "after_url": "http://127.0.0.1/", "allow_local": True}),
                                  (tools.handle_loop_step, {"name": "x", "after_url": "http://127.0.0.1/",
                                                            "allow_local": True})):
                result = json.loads(handler(args))
                self.assertFalse(result["success"])
                self.assertIn("config", result["error"])

    def test_allow_local_defaults_false_and_requires_literal_true(self):
        for config, expected in (({}, False), ({"allow_local": "true"}, False),
                                 ({"allow_local": 1}, False), ({"allow_local": True}, True)):
            with patch.object(tools, "plugin_config", return_value=config):
                self.assertIs(tools.allow_local(), expected)

    def test_config_reader_fails_closed(self):
        with patch.dict("sys.modules", {"hermes_cli.config": None}):
            self.assertEqual(tools.plugin_config(), {})

    def test_pair_passes_config_value_to_engine(self):
        seen = {}

        def fake_pair(*args, **kwargs):
            seen.update(kwargs)
            return {"status": "error", "error": "stop"}

        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HERMES_HOME": home}), \
                patch.object(tools, "plugin_config", return_value={}), \
                patch.object(url_capture, "capture_pair", side_effect=fake_pair):
            tools.handle_compare({"before_url": "https://example.com/", "after_url": "https://example.com/"})
        self.assertIs(seen["allow_local"], False)


def _addresses(*items):
    return [(socket.AF_INET6 if ":" in item else socket.AF_INET, socket.SOCK_STREAM, 6, "",
             (item, 80) if ":" not in item else (item, 80, 0, 0)) for item in items]


class MetadataBlockTests(unittest.TestCase):
    BLOCKED = ("169.254.169.254", "169.254.0.1", "fd00:ec2::254", "fe80::1",
               "::ffff:169.254.169.254", "64:ff9b::a9fe:a9fe")

    def test_metadata_refused_even_with_allow_local(self):
        for address in self.BLOCKED:
            with self.subTest(address=address), \
                    patch.object(network, "resolve", return_value=_addresses(address)):
                for allow in (True, False):
                    with self.assertRaises(network.URLPolicyError):
                        network.destination("http://metadata.example/", allow, 1)
                self.assertIsNotNone(url_capture.validate_url("http://metadata.example/", allow_local=True))

    def test_literal_metadata_ip_refused_with_allow_local(self):
        for url in ("http://169.254.169.254/latest/meta-data/", "http://[fd00:ec2::254]/"):
            with self.assertRaises(network.URLPolicyError):
                network.destination(url, True, 1)

    def test_loopback_still_allowed_with_allow_local(self):
        network.destination("http://127.0.0.1:8080/", True, 1)
        with self.assertRaises(network.URLPolicyError):
            network.destination("http://127.0.0.1:8080/", False, 1)

    def test_guarded_proxy_refuses_metadata_with_allow_local(self):
        import time
        proxy = network.GuardedProxy(True, time.monotonic() + 5)
        try:
            with patch.object(network, "resolve", return_value=_addresses("169.254.169.254")):
                with self.assertRaises(network.URLPolicyError):
                    proxy.connect("http://metadata.example/")
        finally:
            proxy.close()


if __name__ == "__main__":
    unittest.main()
