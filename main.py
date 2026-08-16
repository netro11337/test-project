"""Точка входа: python main.py"""

from __future__ import annotations

import logging

from cart_bot.gui import main

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # webdriver-manager пишет и в свой журнал, и в общий — каждая строка о
    # загрузке драйвера печаталась дважды.
    logging.getLogger("WDM").propagate = False
    main()
