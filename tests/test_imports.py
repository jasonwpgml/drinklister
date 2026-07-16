import builtins
import importlib
import sys


def test_import_without_tkinter(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tkinter" or name.startswith("tkinter."):
            raise ImportError("No tkinter")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("drinklister", None)

    module = importlib.import_module("drinklister")

    assert hasattr(module, "parse_discord_text")
    assert hasattr(module, "extract_orders")
