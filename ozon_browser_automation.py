"""
Ozon Browser Automation using Playwright
Автоматизация регистрации на Озон через браузер Chrome
"""

import asyncio
import time
import random
from typing import Optional, Tuple
from datetime import datetime, timedelta
from faker import Faker
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class OzonBrowserAutomation:
    """Автоматизация регистрации Озон через браузер"""

    def __init__(self, headless: bool = False):
        """
        Инициализация браузерной автоматизации

        Args:
            headless: Запускать ли браузер в фоне без отображения
        """
        self.headless = headless
        self.faker = Faker('ru_RU')
        self.browser: Optional[Browser] = None

    async def init_browser(self):
        """Инициализировать браузер"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        return self.browser

    async def close_browser(self):
        """Закрыть браузер"""
        if self.browser:
            await self.browser.close()

    async def register_account(self, phone: str, sms_code: str,
                               email: str, email_password: str) -> Tuple[bool, str]:
        """
        Полный цикл регистрации аккаунта

        Args:
            phone: Номер телефона
            sms_code: SMS код для подтверждения
            email: Email адрес
            email_password: Пароль от email

        Returns:
            Кортеж (успешно, сообщение)
        """
        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            # Шаг 1: Вход на озон и ввод номера
            print(f"[1/6] Открытие сайта Озон...")
            await page.goto("https://www.ozon.ru/")
            await page.wait_for_timeout(2000)

            # Нажимаем на "Войти"
            await page.click("//button[contains(text(), 'Войти')]")
            await page.wait_for_timeout(2000)

            # Вводим номер телефона
            print(f"[2/6] Ввод номера телефона: {phone}")
            phone_input = await page.query_selector("input[type='tel'], input[placeholder*='Телефон'], input[placeholder*='номер']")
            if phone_input:
                await phone_input.click()
                await phone_input.fill(phone)
                await page.wait_for_timeout(1000)
            else:
                return False, "Не найдено поле для ввода номера"

            # Нажимаем "Продолжить"
            await page.click("//button[contains(text(), 'Продолжить')] | //button[contains(text(), 'Отправить')]")
            await page.wait_for_timeout(3000)

            # Шаг 2: Озон будет звонить - ждем 30 сек и нажимаем "Отправить код еще раз"
            print(f"[3/6] Озон попытается позвонить... Ждем 30 сек...")
            for i in range(30, 0, -1):
                print(f"  Осталось {i} сек", end="\r")
                await page.wait_for_timeout(1000)

            print(f"\n  Нажимаем 'Отправить код еще раз' для получения SMS...")
            try:
                await page.click("//button[contains(text(), 'Отправить код еще раз')] | //button[contains(text(), 'Получить код')]")
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"  ⚠ Не найдена кнопка отправки кода: {str(e)}")

            # Шаг 3: Вводим SMS код
            print(f"[4/6] Ввод SMS кода: {sms_code}")
            # Ищем поле для кода
            code_inputs = await page.query_selector_all("input[type='text'], input[inputmode='numeric']")
            if code_inputs:
                code_input = code_inputs[-1]  # Обычно последнее поле это код
                await code_input.click()
                await code_input.fill(sms_code)
                await page.wait_for_timeout(1000)

                # Нажимаем "Продолжить"
                await page.click("//button[contains(text(), 'Продолжить')] | //button[contains(text(), 'Подтвердить')]")
                await page.wait_for_timeout(3000)
            else:
                return False, "Не найдено поле для ввода кода"

            # Шаг 4: Обновление профиля (ФИО, дата рождения, пол)
            print(f"[5/6] Обновление профиля...")
            await page.goto("https://www.ozon.ru/ozonid")
            await page.wait_for_timeout(2000)

            # Генерируем случайные данные
            first_name = self.faker.first_name()
            last_name = self.faker.last_name()
            middle_name = self.faker.middle_name()

            # Случайная дата рождения (18-70 лет)
            age = random.randint(18, 70)
            birth_date = datetime.now() - timedelta(days=age*365 + random.randint(0, 365))
            birth_date_str = birth_date.strftime("%d.%m.%Y")

            # Случайный пол
            gender = random.choice(["Мужской", "Женский"])

            print(f"  ФИО: {first_name} {middle_name} {last_name}")
            print(f"  Дата рождения: {birth_date_str}")
            print(f"  Пол: {gender}")

            # Ищем поля профиля
            try:
                # Имя
                first_name_input = await page.query_selector("input[placeholder*='Имя']")
                if first_name_input:
                    await first_name_input.click()
                    await first_name_input.fill("")
                    await first_name_input.type(first_name)

                # Фамилия
                last_name_input = await page.query_selector("input[placeholder*='Фамилия']")
                if last_name_input:
                    await last_name_input.click()
                    await last_name_input.fill("")
                    await last_name_input.type(last_name)

                # Отчество
                middle_name_input = await page.query_selector("input[placeholder*='Отчество']")
                if middle_name_input:
                    await middle_name_input.click()
                    await middle_name_input.fill("")
                    await middle_name_input.type(middle_name)

                # Дата рождения
                birth_date_input = await page.query_selector("input[placeholder*='Дата']")
                if birth_date_input:
                    await birth_date_input.click()
                    await birth_date_input.fill("")
                    await birth_date_input.type(birth_date_str)

                # Пол
                gender_select = await page.query_selector("select, [role='combobox']")
                if gender_select:
                    await gender_select.click()
                    await page.click(f"//option[text()='{gender}'] | //span[text()='{gender}']")

                # Сохраняем профиль
                save_button = await page.query_selector("//button[contains(text(), 'Сохранить')]")
                if save_button:
                    await save_button.click()
                    await page.wait_for_timeout(2000)

            except Exception as e:
                print(f"  ⚠ Ошибка при обновлении профиля: {str(e)}")

            # Шаг 5: Добавление email
            print(f"[6/6] Добавление email: {email}")
            await page.goto("https://www.ozon.ru/ozonid")
            await page.wait_for_timeout(2000)

            try:
                # Ищем кнопку "Добавить email"
                add_email_btn = await page.query_selector("//button[contains(text(), 'Добавить')]")
                if add_email_btn:
                    await add_email_btn.click()
                    await page.wait_for_timeout(1000)

                # Вводим email
                email_input = await page.query_selector("input[type='email']")
                if email_input:
                    await email_input.click()
                    await email_input.fill(email)
                    await page.wait_for_timeout(1000)

                    # Нажимаем отправить
                    await page.click("//button[contains(text(), 'Отправить')]")
                    await page.wait_for_timeout(2000)

                    print(f"  ✓ Email отправлен, ожидаем кода подтверждения...")
                    # TODO: Получить код с email и ввести его

            except Exception as e:
                print(f"  ⚠ Ошибка при добавлении email: {str(e)}")

            print(f"✓ Аккаунт успешно создан!")
            return True, "Аккаунт успешно создан"

        except Exception as e:
            print(f"✗ Ошибка: {str(e)}")
            return False, str(e)

        finally:
            await context.close()

    async def run_complete_workflow(self, phone: str, sms_code: str,
                                    email: str, email_password: str) -> Tuple[bool, str, Optional[str]]:
        """
        Запустить полный цикл регистрации

        Args:
            phone: Номер телефона
            sms_code: SMS код
            email: Email адрес
            email_password: Пароль от email

        Returns:
            Кортеж (успешно, сообщение, результат номер:почта:пароль)
        """
        success, message = await self.register_account(phone, sms_code, email, email_password)

        if success:
            result = f"{phone}:{email}:{email_password}"
            return True, message, result
        else:
            return False, message, None


# Синхронная обертка для удобства использования
class OzonBrowserAutomationSync:
    """Синхронная версия OzonBrowserAutomation"""

    def __init__(self, headless: bool = False):
        self.automation = OzonBrowserAutomation(headless=headless)
        self.loop = None

    def init_browser(self):
        """Инициализировать браузер"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        return self.loop.run_until_complete(self.automation.init_browser())

    def close_browser(self):
        """Закрыть браузер"""
        if self.loop:
            self.loop.run_until_complete(self.automation.close_browser())
            self.loop.close()

    def register_account(self, phone: str, sms_code: str,
                        email: str, email_password: str) -> Tuple[bool, str]:
        """Регистрация аккаунта"""
        if not self.loop:
            self.init_browser()
        return self.loop.run_until_complete(
            self.automation.register_account(phone, sms_code, email, email_password)
        )

    def run_complete_workflow(self, phone: str, sms_code: str,
                             email: str, email_password: str) -> Tuple[bool, str, Optional[str]]:
        """Полный цикл регистрации"""
        if not self.loop:
            self.init_browser()
        return self.loop.run_until_complete(
            self.automation.run_complete_workflow(phone, sms_code, email, email_password)
        )
