"""Identity of the toolchain itself.

One place for the product name and version: every surface (logs, CLI, TUI,
Web, docs) reads them from here via ``_config.app_name()`` / ``_config.versions()``.
"""

APP_NAME = 'bookwright'
APP_NAME_ZH = '源码分析成书工具'
APP_TITLE = f'{APP_NAME} — {APP_NAME_ZH}'
TOOL_VERSION = '0.1-dev'
