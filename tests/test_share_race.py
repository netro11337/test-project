import threading
import time
import unittest

import cart_bot.cart as cart_module
from cart_bot.cart import ShareResult, share_cart
from cart_bot.config import Settings
from cart_bot.markets import WB


class SharingDriver:
    """Драйвер, который кладёт ссылку в общий на всех буфер обмена."""

    def __init__(self, clipboard, link, hold=0.05):
        self.clipboard = clipboard
        self.link = link
        self.hold = hold

    # -- то, что нужно share_cart, чтобы дойти до буфера --
    current_url = WB.cart_url

    def find_elements(self, by, selector):
        if selector == WB.cart_ready:
            return [object()]
        if selector == WB.cart_item:
            return [object()]
        if selector in WB.share_buttons or selector in WB.share_confirm:
            return [_Button(self)]
        return []

    def find_element(self, by, selector):
        found = self.find_elements(by, selector)
        if not found:
            raise LookupError(selector)
        return found[0]

    def execute_cdp_cmd(self, name, params):
        return {}

    def execute_script(self, script, *args):
        if "writeText" in script:
            self.clipboard["value"] = args[0]
        return None

    def execute_async_script(self, script):
        return self.clipboard.get("value", "")


class _Button:
    def __init__(self, driver):
        self.driver = driver

    def is_displayed(self):
        return True

    def click(self):
        # Магазин копирует ссылку не мгновенно — за это время в буфер успевал
        # влезть соседний поток.
        time.sleep(self.driver.hold)
        self.driver.clipboard["value"] = self.driver.link


def settings():
    return Settings(market_key="wb", element_timeout=0.3, micro_pause=0.0)


class ShareRaceTest(unittest.TestCase):
    """Ссылка каждого потока должна вести в его собственную корзину."""

    def test_parallel_shares_do_not_swap_links(self):
        clipboard = {"value": ""}
        links = {
            2: "https://www.wildberries.ru/lk/basket/shared/thread-2",
            4: "https://www.wildberries.ru/lk/basket/shared/thread-4",
        }
        results = {}

        def run(thread_id):
            driver = SharingDriver(clipboard, links[thread_id])
            results[thread_id] = share_cart(driver, settings())

        threads = [threading.Thread(target=run, args=(i,)) for i in (2, 4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for thread_id, link in links.items():
            self.assertEqual(
                results[thread_id].url,
                link,
                f"поток {thread_id} получил чужую ссылку",
            )

    def test_lock_serialises_clipboard_work(self):
        # Пока один поток работает с буфером, второй ждёт.
        order = []
        original = cart_module._share_locked

        def traced(driver, cfg, market):
            order.append("in")
            result = original(driver, cfg, market)
            order.append("out")
            return result

        cart_module._share_locked = traced
        try:
            clipboard = {"value": ""}
            threads = [
                threading.Thread(
                    target=share_cart,
                    args=(
                        SharingDriver(clipboard, f"https://www.wildberries.ru/x{i}"),
                        settings(),
                    ),
                )
                for i in range(3)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        finally:
            cart_module._share_locked = original

        self.assertEqual(order, ["in", "out"] * 3, "потоки перекрылись в буфере")


class PendingClipboardPolicyTest(unittest.TestCase):
    def test_fallback_result_is_not_a_share_link(self):
        result = ShareResult(WB.cart_url, "fallback", "буфер небезопасен")
        self.assertFalse(result.is_shared)


if __name__ == "__main__":
    unittest.main()
