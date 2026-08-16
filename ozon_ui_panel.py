"""
Ozon Registration UI Panel
Графический интерфейс для управления регистрацией аккаунтов
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
from datetime import datetime
from megasms_service import MegaSMSService
from ozon_browser_automation import OzonBrowserAutomationSync


class OzonRegistrationPanel:
    """Панель управления регистрацией Озон"""

    def __init__(self, root, api_key: str):
        """
        Инициализация панели

        Args:
            root: Root Tkinter окно
            api_key: API ключ MegaSMS
        """
        self.root = root
        self.root.title("Ozon Auto Registration Panel")
        self.root.geometry("1200x800")
        self.api_key = api_key
        self.sms_service = MegaSMSService(api_key)
        self.browser_automation = None
        self.is_running = False
        self.results = []
        self.emails = []

        # Настройка стиля
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.setup_ui()

    def setup_ui(self):
        """Настройка интерфейса"""
        # Главный контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ===== ЛЕВАЯ ПАНЕЛЬ (INPUT) =====
        left_frame = ttk.LabelFrame(main_container, text="Настройки", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Количество аккаунтов
        ttk.Label(left_frame, text="Количество аккаунтов:").pack(anchor=tk.W, pady=(0, 5))
        self.account_count_var = tk.StringVar(value="5")
        ttk.Spinbox(
            left_frame,
            from_=1,
            to=100,
            textvariable=self.account_count_var,
            width=10
        ).pack(anchor=tk.W, pady=(0, 15))

        # Email список
        ttk.Label(left_frame, text="Список Email (email:пароль):").pack(anchor=tk.W, pady=(0, 5))
        ttk.Button(left_frame, text="Загрузить из файла", command=self.load_emails_from_file).pack(
            anchor=tk.W, pady=(0, 5)
        )

        self.email_text = scrolledtext.ScrolledText(left_frame, height=20, width=40)
        self.email_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Кнопки управления
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_button = ttk.Button(button_frame, text="▶ Начать", command=self.start_registration)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.pause_button = ttk.Button(button_frame, text="⏸ Пауза", command=self.pause_registration, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(button_frame, text="⏹ Стоп", command=self.stop_registration, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        # Проверка баланса
        ttk.Button(left_frame, text="Проверить баланс MegaSMS", command=self.check_balance).pack(
            fill=tk.X, pady=(0, 10)
        )

        # ===== ПРАВАЯ ПАНЕЛЬ (OUTPUT) =====
        right_frame = ttk.LabelFrame(main_container, text="Логи и результаты", padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Табы для разных видов информации
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Таб с логами
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="Логи")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=25, width=50, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Таб с результатами
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="Результаты")

        ttk.Button(results_frame, text="Копировать результаты", command=self.copy_results).pack(
            pady=5
        )
        ttk.Button(results_frame, text="Сохранить в файл", command=self.save_results).pack(
            pady=5
        )

        self.results_text = scrolledtext.ScrolledText(results_frame, height=25, width=50, state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=(0, 0), pady=(5, 0))

        # Прогресс бар
        progress_frame = ttk.Frame(main_container)
        progress_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(progress_frame, text="Прогресс:").pack(side=tk.LEFT, padx=(0, 10))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=400
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.LEFT, padx=(10, 0))

        # Статус бар
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(status_frame, text="Статус:").pack(side=tk.LEFT, padx=(0, 10))
        self.status_label = ttk.Label(status_frame, text="Готов", foreground="green")
        self.status_label.pack(side=tk.LEFT)

    def log(self, message: str):
        """Добавить сообщение в логи"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    def update_status(self, status: str, color: str = "black"):
        """Обновить статус"""
        self.status_label.config(text=status, foreground=color)
        self.root.update()

    def update_progress(self, current: int, total: int):
        """Обновить прогресс бар"""
        if total > 0:
            percentage = (current / total) * 100
            self.progress_var.set(percentage)
            self.progress_label.config(text=f"{int(percentage)}% ({current}/{total})")
        self.root.update()

    def add_result(self, result: str):
        """Добавить результат"""
        self.results.append(result)
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, result + "\n")
        self.results_text.see(tk.END)
        self.results_text.config(state=tk.DISABLED)
        self.root.update()

    def load_emails_from_file(self):
        """Загрузить email список из файла"""
        filename = filedialog.askopenfilename(
            title="Выберите файл с email адресами",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.email_text.delete(1.0, tk.END)
                self.email_text.insert(tk.END, content)
                self.log(f"✓ Загружено {len(content.split())} email адресов")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить файл: {str(e)}")

    def check_balance(self):
        """Проверить баланс MegaSMS"""
        threading.Thread(target=self._check_balance_thread, daemon=True).start()

    def _check_balance_thread(self):
        """Поток проверки баланса"""
        self.log("Проверка баланса MegaSMS...")
        balance = self.sms_service.get_balance()
        if balance is not None:
            self.log(f"✓ Баланс: {balance} руб")
            messagebox.showinfo("Баланс", f"Баланс MegaSMS: {balance} руб")
        else:
            self.log("✗ Не удалось получить баланс")
            messagebox.showerror("Ошибка", "Не удалось получить баланс MegaSMS")

    def start_registration(self):
        """Начать регистрацию"""
        # Получаем данные
        try:
            account_count = int(self.account_count_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное количество аккаунтов")
            return

        email_text = self.email_text.get(1.0, tk.END).strip()
        if not email_text:
            messagebox.showerror("Ошибка", "Введите список email адресов")
            return

        # Парсим email список
        self.emails = []
        for line in email_text.split('\n'):
            line = line.strip()
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    self.emails.append({'email': parts[0], 'password': parts[1]})

        if len(self.emails) < account_count:
            messagebox.showerror("Ошибка", f"Email адресов ({len(self.emails)}) меньше чем нужно ({account_count})")
            return

        # Очищаем результаты
        self.results = []
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state=tk.DISABLED)

        # Запускаем в отдельном потоке
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.NORMAL)

        thread = threading.Thread(
            target=self._registration_thread,
            args=(account_count,),
            daemon=True
        )
        thread.start()

    def _registration_thread(self, account_count: int):
        """Поток регистрации"""
        self.update_status("Инициализация браузера...", "blue")
        self.log("Инициализация браузера Chrome...")

        try:
            self.browser_automation = OzonBrowserAutomationSync(headless=False)
            self.browser_automation.init_browser()
            self.log("✓ Браузер инициализирован")

            for i in range(account_count):
                if not self.is_running:
                    break

                self.update_status(f"Обработка аккаунта {i+1}/{account_count}", "blue")
                self.log(f"\n{'='*50}")
                self.log(f"Аккаунт {i+1}/{account_count}")
                self.log(f"{'='*50}")

                email_data = self.emails[i]
                email = email_data['email']
                email_password = email_data['password']

                # Получаем номер телефона
                self.log("Получение номера телефона с MegaSMS (Ozончик)...")
                phone_data = self.sms_service.get_phone_number("ozончик")

                if not phone_data:
                    self.log("✗ Не удалось получить номер телефона")
                    self.update_progress(i, account_count)
                    continue

                phone = phone_data['phone']
                activation_id = phone_data['activation_id']
                self.log(f"✓ Получен номер: {phone}")

                # Получаем SMS код
                self.log("Ожидание SMS кода...")
                sms_code = self.sms_service.wait_for_sms(activation_id, max_wait=120, check_interval=5)

                if not sms_code:
                    self.log("✗ SMS код не получен")
                    self.sms_service.cancel_activation(activation_id)
                    self.update_progress(i, account_count)
                    continue

                self.log(f"✓ SMS код получен: {sms_code}")

                # Регистрируем аккаунт через браузер
                self.log("Регистрация через браузер...")
                try:
                    success, message, result = self.browser_automation.run_complete_workflow(
                        phone, sms_code, email, email_password
                    )

                    if success:
                        self.log(f"✓ {message}")
                        self.add_result(result)
                        self.sms_service.finish_activation(activation_id)
                    else:
                        self.log(f"✗ Ошибка: {message}")
                        self.sms_service.cancel_activation(activation_id)

                except Exception as e:
                    self.log(f"✗ Ошибка регистрации: {str(e)}")
                    self.sms_service.cancel_activation(activation_id)

                self.update_progress(i + 1, account_count)

            self.update_status("Завершено", "green")
            self.log(f"\n✓ Регистрация завершена! Успешно: {len(self.results)}/{account_count}")

        except Exception as e:
            self.log(f"✗ Критическая ошибка: {str(e)}")
            self.update_status("Ошибка", "red")

        finally:
            if self.browser_automation:
                self.browser_automation.close_browser()
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)

    def pause_registration(self):
        """Пауза регистрации"""
        self.is_running = False
        self.update_status("На паузе", "orange")
        self.log("⏸ Регистрация приостановлена")

    def stop_registration(self):
        """Остановить регистрацию"""
        self.is_running = False
        self.update_status("Остановлено", "red")
        self.log("⏹ Регистрация остановлена")

    def copy_results(self):
        """Копировать результаты в буфер обмена"""
        results_str = "\n".join(self.results)
        self.root.clipboard_clear()
        self.root.clipboard_append(results_str)
        messagebox.showinfo("Успех", f"Скопировано {len(self.results)} результатов")

    def save_results(self):
        """Сохранить результаты в файл"""
        filename = filedialog.asksaveasfilename(
            title="Сохранить результаты",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json")]
        )
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump({
                            "results": self.results,
                            "total": len(self.results),
                            "timestamp": datetime.now().isoformat()
                        }, f, ensure_ascii=False, indent=2)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("\n".join(self.results))

                messagebox.showinfo("Успех", f"Результаты сохранены в {filename}")
                self.log(f"✓ Результаты сохранены в {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {str(e)}")


def main():
    """Главная функция"""
    api_key = "lpkfsipROdyEIHPv"  # API ключ MegaSMS

    root = tk.Tk()
    panel = OzonRegistrationPanel(root, api_key)
    root.mainloop()


if __name__ == "__main__":
    main()
