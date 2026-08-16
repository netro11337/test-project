import unittest

from ozon_cart.skus import dedupe_batches, parse_skus, split_evenly


class ParseSkusTest(unittest.TestCase):
    def test_commas_and_newlines(self):
        text = "123456789, 987654321\n555444333;111222333"
        self.assertEqual(
            parse_skus(text), ["123456789", "987654321", "555444333", "111222333"]
        )

    def test_extracts_from_product_url(self):
        text = "https://www.ozon.ru/product/chehol-dlya-iphone-15-1234567890/?at=abc"
        self.assertEqual(parse_skus(text), ["1234567890"])

    def test_url_with_digits_in_slug(self):
        text = "https://www.ozon.ru/product/naushniki-air-3-pro-2024-987654321/"
        self.assertEqual(parse_skus(text), ["987654321"])

    def test_dedupes_preserving_order(self):
        self.assertEqual(
            parse_skus("111111111, 222222222, 111111111"),
            ["111111111", "222222222"],
        )

    def test_ignores_short_numbers_and_noise(self):
        self.assertEqual(parse_skus("шт 5, 42, ---"), [])

    def test_empty_input(self):
        self.assertEqual(parse_skus(""), [])
        self.assertEqual(parse_skus("   \n  "), [])


class SplitEvenlyTest(unittest.TestCase):
    def test_round_robin_distribution(self):
        skus = [str(i) for i in range(1, 8)]
        self.assertEqual(
            split_evenly(skus, 3), [["1", "4", "7"], ["2", "5"], ["3", "6"]]
        )

    def test_more_threads_than_skus(self):
        self.assertEqual(split_evenly(["1", "2"], 4), [["1"], ["2"], [], []])

    def test_single_thread(self):
        self.assertEqual(split_evenly(["1", "2"], 1), [["1", "2"]])

    def test_rejects_zero_threads(self):
        with self.assertRaises(ValueError):
            split_evenly(["1"], 0)


class DedupeBatchesTest(unittest.TestCase):
    def test_dedupes_within_thread(self):
        self.assertEqual(dedupe_batches([["1", "1", "2"]]), [["1", "2"]])

    def test_keeps_same_sku_across_threads(self):
        # Разные корзины — один и тот же товар в двух потоках допустим.
        self.assertEqual(dedupe_batches([["1"], ["1"]]), [["1"], ["1"]])


if __name__ == "__main__":
    unittest.main()
