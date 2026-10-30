"""Production dashboard server (waitress) using host/port from config.toml.

Run:  python -m app.serve
"""

from __future__ import annotations

import logging

from waitress import serve

from .config import load_config
from .logging_setup import setup_logging
from .web import create_app


def main() -> None:
    config = load_config()
    setup_logging("INFO", config.web.log_file)
    logging.getLogger("app.serve").info(
        "Dashboard on http://%s:%d (config %s)", config.web.host, config.web.port, config.source
    )
    serve(create_app(config), host=config.web.host, port=config.web.port, threads=4)


if __name__ == "__main__":
    main()
