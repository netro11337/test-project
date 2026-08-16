"""Точка входа: python main.py"""

from __future__ import annotations

import logging

from ozon_cart.gui import main

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()
