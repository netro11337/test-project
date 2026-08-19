import unittest

from cart_bot.cart import _count_shareish, _wait_for_dialog, find_share_confirm
from cart_bot.config import Settings
from cart_bot.markets import OZON, WB

try:
    from lxml import etree

    HAS_LXML = True
except ImportError:  # pragma: no cover
    HAS_LXML = False


# Окно Ozon: заголовок «Поделиться списком» и синяя кнопка с числом товаров.
OZON_MODAL = """
<html><body>
  <button>Поделиться</button>
  <div class="ozon-modal">
    <h2>Поделиться списком</h2>
    <div>Товары из вашей корзины</div>
    <button><span>Поделиться</span><span>10 товаров</span></button>
  </div>
</body></html>
"""


class FakeElement:
    def __init__(self, name):
        self.name = name

    def is_displayed(self):
        return True


class FakeDriver:
    def __init__(self, matches=None):
        self.matches = matches or {}

    def find_elements(self, by, xpath):
        return self.matches.get(xpath, [])


@unittest.skipUnless(HAS_LXML, "нужен lxml для разбора разметки")
class OzonModalMarkupTest(unittest.TestCase):
    """Окно без role=dialog: раньше кнопка в нём не находилась."""

    def setUp(self):
        self.doc = etree.fromstring(OZON_MODAL)

    def test_confirm_button_is_found(self):
        for xpath in OZON.share_confirm:
            found = self.doc.xpath(xpath)
            if found:
                text = "".join(found[-1].itertext())
                self.assertIn("Поделиться", text)
                return
        self.fail("кнопка подтверждения не найдена ни одним селектором")

    def test_dialog_is_detected_without_role_attribute(self):
        self.assertTrue(
            self.doc.xpath(OZON.share_dialog), "окно не опознано как открытое"
        )


class WaitForDialogTest(unittest.TestCase):
    def test_dialog_present(self):
        driver = FakeDriver({OZON.share_dialog: [FakeElement("окно")]})
        self.assertTrue(_wait_for_dialog(driver, OZON, 0.1))

    def test_no_dialog(self):
        self.assertFalse(_wait_for_dialog(FakeDriver(), OZON, 0.1))


class ConfirmFallbackTest(unittest.TestCase):
    """Широкий вариант ловит вторую кнопку, не трогая уже нажатую."""

    def setUp(self):
        self.cfg = Settings(element_timeout=0.0)

    def test_broad_selector_skips_the_clicked_button(self):
        header = FakeElement("шапка")
        modal = FakeElement("окно")
        broad = OZON.share_confirm[-2]
        driver = FakeDriver({broad: [header, modal]})
        found, xpath = find_share_confirm(driver, OZON, header, 0.0)
        self.assertIs(found, modal)
        self.assertEqual(xpath, broad)

    def test_nothing_when_only_the_clicked_button_exists(self):
        header = FakeElement("шапка")
        driver = FakeDriver({OZON.share_confirm[-2]: [header]})
        found, _ = find_share_confirm(driver, OZON, header, 0.0)
        self.assertIsNone(found)

    def test_counts_similar_buttons_for_the_log(self):
        driver = FakeDriver(
            {OZON.share_confirm[-2]: [FakeElement("a"), FakeElement("b")]}
        )
        self.assertEqual(_count_shareish(driver, OZON), 2)

    def test_both_markets_have_a_broad_fallback(self):
        for market in (OZON, WB):
            self.assertTrue(
                any(x == "//button[contains(., 'оделиться')]" for x in market.share_confirm),
                f"{market.key}: нет широкого варианта",
            )


if __name__ == "__main__":
    unittest.main()
