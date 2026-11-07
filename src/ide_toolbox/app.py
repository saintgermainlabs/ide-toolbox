from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .adapters.registry import all_adapters, build_allowlist
    from .core.applog import setup_logging
    from .core.context import ScanContext
    from .core.settings import Settings
    from .ui.main_window import MainWindow

    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("IDE Toolbox")
    app.setDesktopFileName("ide-toolbox")
    settings = Settings().load()
    ctx = ScanContext.from_environment(settings.project_roots)
    ctx.runner.allowlist = build_allowlist()
    win = MainWindow(all_adapters(), ctx, settings)
    win.show()
    win.scan_all()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
