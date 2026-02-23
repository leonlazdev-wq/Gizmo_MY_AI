from modules.tools.calculator import CalculatorTool
from modules.tools.file_reader import FileReaderTool
from modules.tools.python_runner import PythonRunnerTool
from modules.tools.web_search_tool import WebSearchTool


def default_tools():
    return {
        "calculator": CalculatorTool(),
        "python_runner": PythonRunnerTool(),
        "file_reader": FileReaderTool(),
        "web_search": WebSearchTool(),
    }
