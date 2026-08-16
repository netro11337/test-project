"""
Модульные тесты для Ozon Auto-Registration системы
"""

import unittest
from ozon_autoregister import OzonAutoRegister, OzonAccount


class TestOzonAutoRegister(unittest.TestCase):
    """Тесты для класса OzonAutoRegister"""

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.registrar = OzonAutoRegister()

    def test_validate_email_valid(self):
        """Тест валидации корректного email"""
        self.assertTrue(self.registrar.validate_email("user@example.com"))
        self.assertTrue(self.registrar.validate_email("test.user+tag@example.co.uk"))

    def test_validate_email_invalid(self):
        """Тест валидации некорректного email"""
        self.assertFalse(self.registrar.validate_email("not_an_email"))
        self.assertFalse(self.registrar.validate_email("user@"))
        self.assertFalse(self.registrar.validate_email("@example.com"))
        self.assertFalse(self.registrar.validate_email("user @example.com"))

    def test_validate_phone_valid(self):
        """Тест валидации корректного номера телефона"""
        self.assertTrue(self.registrar.validate_phone("+79101234567"))
        self.assertTrue(self.registrar.validate_phone("89101234567"))
        self.assertTrue(self.registrar.validate_phone("+7-910-123-4567"))

    def test_validate_phone_invalid(self):
        """Тест валидации некорректного номера телефона"""
        self.assertFalse(self.registrar.validate_phone("123"))
        self.assertFalse(self.registrar.validate_phone("+14155552671"))  # США
        self.assertFalse(self.registrar.validate_phone("+7910123456"))  # Недостаточно цифр

    def test_validate_password_valid(self):
        """Тест валидации корректного пароля"""
        is_valid, msg = self.registrar.validate_password("StrongPass123")
        self.assertTrue(is_valid)
        self.assertEqual(msg, "OK")

        is_valid, msg = self.registrar.validate_password("AnotherPass456")
        self.assertTrue(is_valid)

    def test_validate_password_too_short(self):
        """Тест на слишком короткий пароль"""
        is_valid, msg = self.registrar.validate_password("Short1")
        self.assertFalse(is_valid)
        self.assertIn("8 символов", msg)

    def test_validate_password_no_uppercase(self):
        """Тест на отсутствие заглавных букв"""
        is_valid, msg = self.registrar.validate_password("lowercase123")
        self.assertFalse(is_valid)
        self.assertIn("заглавную", msg)

    def test_validate_password_no_lowercase(self):
        """Тест на отсутствие строчных букв"""
        is_valid, msg = self.registrar.validate_password("UPPERCASE123")
        self.assertFalse(is_valid)
        self.assertIn("строчную", msg)

    def test_validate_password_no_digits(self):
        """Тест на отсутствие цифр"""
        is_valid, msg = self.registrar.validate_password("NoDigitsHere")
        self.assertFalse(is_valid)
        self.assertIn("цифру", msg)

    def test_validate_account_data_valid(self):
        """Тест валидации корректных данных аккаунта"""
        account = OzonAccount(
            email="user@example.com",
            password="StrongPass123",
            phone="+79101234567",
            first_name="Иван",
            last_name="Петров"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertTrue(valid)
        self.assertEqual(msg, "OK")

    def test_validate_account_data_invalid_email(self):
        """Тест на некорректный email в данных аккаунта"""
        account = OzonAccount(
            email="not_an_email",
            password="StrongPass123",
            phone="+79101234567",
            first_name="Иван",
            last_name="Петров"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertFalse(valid)
        self.assertIn("email", msg)

    def test_validate_account_data_invalid_phone(self):
        """Тест на некорректный телефон в данных аккаунта"""
        account = OzonAccount(
            email="user@example.com",
            password="StrongPass123",
            phone="123",
            first_name="Иван",
            last_name="Петров"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertFalse(valid)
        self.assertIn("телефон", msg)

    def test_validate_account_data_weak_password(self):
        """Тест на слабый пароль в данных аккаунта"""
        account = OzonAccount(
            email="user@example.com",
            password="weak",
            phone="+79101234567",
            first_name="Иван",
            last_name="Петров"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertFalse(valid)

    def test_validate_account_data_short_name(self):
        """Тест на слишком короткое имя"""
        account = OzonAccount(
            email="user@example.com",
            password="StrongPass123",
            phone="+79101234567",
            first_name="И",
            last_name="Петров"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertFalse(valid)

    def test_validate_account_data_short_lastname(self):
        """Тест на слишком короткую фамилию"""
        account = OzonAccount(
            email="user@example.com",
            password="StrongPass123",
            phone="+79101234567",
            first_name="Иван",
            last_name="П"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertFalse(valid)

    def test_normalize_phone(self):
        """Тест нормализации номера телефона"""
        self.assertEqual(self.registrar._normalize_phone("89101234567"), "+79101234567")
        self.assertEqual(self.registrar._normalize_phone("+79101234567"), "+79101234567")
        self.assertEqual(self.registrar._normalize_phone("7-910-123-4567"), "+79101234567")

    def test_ozon_account_creation(self):
        """Тест создания объекта OzonAccount"""
        account = OzonAccount(
            email="test@example.com",
            password="TestPass123",
            phone="+79101234567",
            first_name="Тест",
            last_name="Пользователь"
        )

        self.assertEqual(account.email, "test@example.com")
        self.assertEqual(account.password, "TestPass123")
        self.assertEqual(account.phone, "+79101234567")
        self.assertEqual(account.first_name, "Тест")
        self.assertEqual(account.last_name, "Пользователь")
        self.assertIsNone(account.account_id)
        self.assertIsNone(account.created_at)

    def test_error_collection(self):
        """Тест сбора ошибок"""
        account1 = OzonAccount(
            email="invalid_email",
            password="StrongPass123",
            phone="+79101234567",
            first_name="Test",
            last_name="User"
        )

        account2 = OzonAccount(
            email="user@example.com",
            password="weak",
            phone="+79101234567",
            first_name="Test",
            last_name="User"
        )

        # Попытка регистрации с невалидными данными
        self.registrar.register_account(account1)
        self.registrar.register_account(account2)

        # Проверка, что ошибки накопились
        errors = self.registrar.get_errors()
        self.assertGreater(len(errors), 0)


class TestEdgeCases(unittest.TestCase):
    """Тесты граничных случаев"""

    def setUp(self):
        self.registrar = OzonAutoRegister()

    def test_email_with_many_dots(self):
        """Тест email с множественными точками"""
        self.assertTrue(self.registrar.validate_email("user.name.test@example.com"))

    def test_email_with_numbers(self):
        """Тест email с цифрами"""
        self.assertTrue(self.registrar.validate_email("user123@example456.com"))

    def test_password_exactly_8_chars(self):
        """Тест пароля ровно с 8 символами"""
        is_valid, _ = self.registrar.validate_password("Pass1234")
        self.assertTrue(is_valid)

    def test_password_with_special_chars(self):
        """Тест пароля со специальными символами"""
        is_valid, _ = self.registrar.validate_password("Pass123!@#")
        self.assertTrue(is_valid)

    def test_phone_with_extra_formatting(self):
        """Тест телефона с дополнительным форматированием"""
        self.assertTrue(self.registrar.validate_phone("+7 (910) 123-45-67"))

    def test_unicode_name(self):
        """Тест имена с юникодом"""
        account = OzonAccount(
            email="user@example.com",
            password="StrongPass123",
            phone="+79101234567",
            first_name="Иван",
            last_name="Петров"
        )
        valid, msg = self.registrar.validate_account_data(account)
        self.assertTrue(valid)


def run_tests():
    """Запуск всех тестов"""
    # Создание test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Добавление тестов
    suite.addTests(loader.loadTestsFromTestCase(TestOzonAutoRegister))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    # Запуск тестов
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Возврат статуса
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
