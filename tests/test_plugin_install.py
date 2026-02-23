from modules.plugin_manager import enable_plugin, install_plugin, list_plugins


def test_plugin_install_enable():
    install_plugin("dev_tools/sample_plugin")
    enable_plugin("sample_plugin")
    plugins = list_plugins()
    names = [p["name"] for p in plugins]
    assert "sample_plugin" in names
    assert any(p["name"] == "sample_plugin" and p["enabled"] for p in plugins)
