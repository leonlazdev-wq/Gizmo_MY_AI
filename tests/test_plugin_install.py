from modules.plugin_manager import enable_plugin, install_plugin, list_plugins


def test_plugin_install_and_enable():
    name = install_plugin("dev_tools/sample_plugin")
    assert name == "sample_plugin"
    enable_plugin(name)
    plugins = list_plugins()
    sample = [p for p in plugins if p["name"] == "sample_plugin"][0]
    assert sample["enabled"] is True
