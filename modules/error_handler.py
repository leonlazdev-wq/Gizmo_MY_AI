"""User-friendly error formatting utilities."""

from __future__ import annotations

import logging
import traceback

logger = logging.getLogger(__name__)


class UserFriendlyError(Exception):
    """Exception containing UI-safe message and suggestions."""

    def __init__(self, user_message: str, technical_details: str | None = None, suggestions: list | None = None):
        self.user_message = user_message
        self.technical_details = technical_details or traceback.format_exc()
        self.suggestions = suggestions or []
        super().__init__(user_message)

    def format_for_ui(self) -> str:
        message = f"❌ **Error:** {self.user_message}\n\n"
        if self.suggestions:
            message += "**💡 Suggestions:**\n"
            for suggestion in self.suggestions:
                message += f"- {suggestion}\n"

        message += "\n<details><summary>Technical Details (click to expand)</summary>\n\n"
        message += f"```\n{self.technical_details}\n```\n"
        message += "</details>"
        return message


ERROR_MESSAGES = {
    "model_not_loaded": {
        "message": "No model is currently loaded",
        "suggestions": [
            "Go to the Model tab and select a model",
            "Check if you have any models downloaded in user_data/models",
            "Try the Model Hub tab to download a model",
        ],
    },
    "out_of_memory": {
        "message": "Ran out of memory during generation",
        "suggestions": [
            "Try reducing the Max Tokens setting",
            "Use a smaller model",
            "Reduce the Context Size parameter",
            "Enable GPU layers offloading if available",
        ],
    },
    "invalid_prompt": {
        "message": "The prompt could not be processed",
        "suggestions": [
            "Check for special characters that might cause issues",
            "Try a simpler prompt first",
            "Check the Prompt Engineering Guide in the Learning Center",
        ],
    },
}


def handle_error(error_key: str, exception: Exception | None = None) -> str:
    if error_key in ERROR_MESSAGES:
        config = ERROR_MESSAGES[error_key]
        technical = str(exception) if exception else traceback.format_exc()
        error = UserFriendlyError(config['message'], technical, config['suggestions'])
        logger.error("error: %s", error_key, exc_info=True)
        return error.format_for_ui()

    return f"❌ An unexpected error occurred: {exception}"
