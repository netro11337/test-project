"""Tkinter-интерфейс: настройка потоков, запуск сборки, ссылки на корзины."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List

from .config import Settings, ensure_app_dir
from .runner import CartResult, CartRunner, Event, EventKind, open_cart_in_browser
from .skus import MAX_SKU, MIN_SKU, dedupe_batches, parse_skus, split_evenly

MAX_THREADS = 20
POLL_MS = 80


class OzonCartApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=10)
        self.master.title("Ozon — параллельная сборка корзин")
        self.master.geometry("1180x780")
        self.master.minsize(980, 660)
        self.grid(row=0, column=0, sticky="nsew")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)

        self.cfg = Settings()
        self.events: "queue.Queue[Event]" = queue.Queue()
        self.runner: CartRunner | None = None
        self.run_thread: threading.Thread | None = None
        self.sku_inputs: List[ScrolledText] = []
        self.carts: Dict[int, CartResult] = {}
        self.opened_browsers: List[object] = []

        self._build_settings()
        self._build_body()
        self._build_footer()
        self._rebuild_tabs()
        self.after(POLL_MS, self._pump_events)

    # ------------------------------------------------------------------ UI

    def _build_settings(self) -> None:
        box = ttk.LabelFrame(self, text="Настройки", padding=8)
        box.grid(row=0, column=0, sticky="ew")
        box.columnconfigure(20, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.threads_var = tk.IntVar(value=4)
        self.workers_var = tk.IntVar(value=4)
        self.headless_var = tk.BooleanVar(value=True)
        self.images_var = tk.BooleanVar(value=True)
        self.timeout_var = tk.DoubleVar(value=5.0)
        self.pause_var = tk.DoubleVar(value=0.35)
        self.retries_var = tk.IntVar(value=1)

        ttk.Label(box, text="Потоков (корзин):").grid(row=0, column=0, padx=(0, 4))
        threads = ttk.Spinbox(
            box,
            from_=1,
            to=MAX_THREADS,
            width=5,
            textvariable=self.threads_var,
            command=self._rebuild_tabs,
        )
        threads.grid(row=0, column=1, padx=(0, 12))
        threads.bind("<Return>", lambda _e: self._rebuild_tabs())
        threads.bind("<FocusOut>", lambda _e: self._rebuild_tabs())

        ttk.Label(box, text="Одновременно:").grid(row=0, column=2, padx=(0, 4))
        ttk.Spinbox(
            box, from_=1, to=MAX_THREADS, width=5, textvariable=self.workers_var
        ).grid(row=0, column=3, padx=(0, 12))

        ttk.Label(box, text="Таймаут, с:").grid(row=0, column=4, padx=(0, 4))
        ttk.Spinbox(
            box,
            from_=2.0,
            to=15.0,
            increment=0.5,
            width=5,
            textvariable=self.timeout_var,
        ).grid(row=0, column=5, padx=(0, 12))

        ttk.Label(box, text="Пауза, с:").grid(row=0, column=6, padx=(0, 4))
        ttk.Spinbox(
            box,
            from_=0.0,
            to=2.0,
            increment=0.05,
            width=5,
            textvariable=self.pause_var,
        ).grid(row=0, column=7, padx=(0, 12))

        ttk.Label(box, text="Ретраев:").grid(row=0, column=8, padx=(0, 4))
        ttk.Spinbox(
            box, from_=0, to=3, width=4, textvariable=self.retries_var
        ).grid(row=0, column=9, padx=(0, 12))

        ttk.Checkbutton(box, text="Headless", variable=self.headless_var).grid(
            row=0, column=10, padx=(0, 8)
        )
        ttk.Checkbutton(box, text="Без картинок", variable=self.images_var).grid(
            row=0, column=11
        )

    def _build_body(self) -> None:
        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.grid(row=1, column=0, sticky="nsew", pady=8)

        left = ttk.Frame(pane)
        pane.add(left, weight=3)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(
            left, text="Общий список SKU (можно ссылками, через запятую или строками)"
        ).grid(row=0, column=0, sticky="w")
        self.bulk_input = ScrolledText(left, height=5, wrap="word")
        self.bulk_input.grid(row=1, column=0, sticky="ew", pady=(2, 4))

        bar = ttk.Frame(left)
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(
            bar, text="Разбить по потокам", command=self._distribute
        ).pack(side="left")
        ttk.Button(bar, text="Очистить всё", command=self._clear_all).pack(
            side="left", padx=6
        )
        self.count_label = ttk.Label(bar, text="SKU: 0")
        self.count_label.pack(side="right")

        self.tabs = ttk.Notebook(left)
        self.tabs.grid(row=3, column=0, sticky="nsew")

        right = ttk.Frame(pane)
        pane.add(right, weight=4)
        right.rowconfigure(1, weight=2)
        right.rowconfigure(4, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Статус потоков").grid(row=0, column=0, sticky="w")
        columns = ("thread", "status", "progress", "fails", "time", "cart")
        self.tree = ttk.Treeview(
            right, columns=columns, show="headings", selectmode="browse"
        )
        for col, title, width in (
            ("thread", "Поток", 60),
            ("status", "Статус", 190),
            ("progress", "Добавлено", 90),
            ("fails", "Ошибок", 70),
            ("time", "Время", 70),
            ("cart", "Корзина", 210),
        ):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(2, 4))

        cart_bar = ttk.Frame(right)
        cart_bar.grid(row=2, column=0, sticky="ew")
        ttk.Button(
            cart_bar, text="Копировать ссылку", command=self._copy_selected
        ).pack(side="left")
        ttk.Button(
            cart_bar, text="Открыть корзину", command=self._open_selected
        ).pack(side="left", padx=6)
        ttk.Button(
            cart_bar, text="Копировать все ссылки", command=self._copy_all
        ).pack(side="left")

        ttk.Label(
            right,
            foreground="#666",
            text=(
                "Корзина Ozon привязана к сессии: адрес у всех один "
                "(ozon.ru/cart), но каждый поток держит свою в своём профиле "
                "Chrome. Кнопка «Открыть корзину» поднимает нужную."
            ),
            wraplength=520,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(6, 2))

        self.log = ScrolledText(right, height=10, wrap="word", state="disabled")
        self.log.grid(row=4, column=0, sticky="nsew")

    def _build_footer(self) -> None:
        footer = ttk.Frame(self)
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(
            footer, text="Собрать корзины", command=self._start
        )
        self.start_btn.grid(row=0, column=0)
        self.cancel_btn = ttk.Button(
            footer, text="Отмена", command=self._cancel, state="disabled"
        )
        self.cancel_btn.grid(row=0, column=1, sticky="w", padx=6)

        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.grid(row=0, column=2, sticky="ew", padx=6)
        footer.columnconfigure(2, weight=1)

        self.status_label = ttk.Label(footer, text="Готов")
        self.status_label.grid(row=0, column=3, sticky="e")

    # --------------------------------------------------------------- вкладки

    def _rebuild_tabs(self) -> None:
        """Пересобирает вкладки под новое число потоков, сохраняя введённое."""
        try:
            wanted = max(1, min(MAX_THREADS, int(self.threads_var.get())))
        except (tk.TclError, ValueError):
            return
        if wanted == len(self.sku_inputs):
            return

        saved = [widget.get("1.0", "end").strip() for widget in self.sku_inputs]
        for tab in self.tabs.tabs():
            self.tabs.forget(tab)
        self.sku_inputs.clear()

        for index in range(wanted):
            frame = ttk.Frame(self.tabs, padding=4)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            text = ScrolledText(frame, height=12, wrap="word", undo=True)
            text.grid(row=0, column=0, sticky="nsew")
            text.bind("<KeyRelease>", lambda _e: self._refresh_count())
            if index < len(saved):
                text.insert("1.0", saved[index])
            self.tabs.add(frame, text=f"Поток {index + 1}")
            self.sku_inputs.append(text)

        self._refresh_count()

    def _collect_batches(self) -> List[List[str]]:
        batches = [parse_skus(widget.get("1.0", "end")) for widget in self.sku_inputs]
        return dedupe_batches(batches)

    def _distribute(self) -> None:
        skus = parse_skus(self.bulk_input.get("1.0", "end"))
        if not skus:
            messagebox.showwarning("Пусто", "В общем списке не нашлось ни одного SKU.")
            return
        batches = split_evenly(skus, len(self.sku_inputs))
        for widget, batch in zip(self.sku_inputs, batches):
            widget.delete("1.0", "end")
            widget.insert("1.0", "\n".join(batch))
        self._refresh_count()
        self._append_log(
            f"Разложил {len(skus)} SKU по {len(self.sku_inputs)} потокам."
        )

    def _clear_all(self) -> None:
        self.bulk_input.delete("1.0", "end")
        for widget in self.sku_inputs:
            widget.delete("1.0", "end")
        self._refresh_count()

    def _refresh_count(self) -> None:
        batches = self._collect_batches()
        total = sum(len(batch) for batch in batches)
        parts = ", ".join(str(len(batch)) for batch in batches)
        self.count_label.config(text=f"SKU: {total}  ({parts})")

    # ----------------------------------------------------------------- запуск

    def _read_settings(self) -> Settings:
        cfg = Settings()
        cfg.headless = bool(self.headless_var.get())
        cfg.block_images = bool(self.images_var.get())
        cfg.page_load_timeout = float(self.timeout_var.get())
        cfg.element_timeout = float(self.timeout_var.get())
        cfg.micro_pause = float(self.pause_var.get())
        cfg.retries = int(self.retries_var.get())
        cfg.max_workers = max(1, int(self.workers_var.get()))
        return cfg

    def _start(self) -> None:
        if self.run_thread and self.run_thread.is_alive():
            return

        batches = self._collect_batches()
        total = sum(len(batch) for batch in batches)
        if total == 0:
            messagebox.showwarning("Пусто", "Не введено ни одного SKU.")
            return
        if not (MIN_SKU <= total <= MAX_SKU):
            proceed = messagebox.askyesno(
                "Необычный объём",
                f"Введено {total} SKU, ожидается от {MIN_SKU} до {MAX_SKU}.\n"
                "Всё равно продолжить?",
            )
            if not proceed:
                return

        self.cfg = self._read_settings()
        ensure_app_dir()
        self.carts.clear()
        self._reset_tree(batches)
        self.progress.config(maximum=total, value=0)
        self._done_count = 0
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.status_label.config(text="Собираю…")
        self._append_log(f"Старт: {total} SKU в {len([b for b in batches if b])} поток(ах).")

        self.runner = CartRunner(self.cfg, batches, self.events.put)
        self.run_thread = threading.Thread(target=self.runner.run, daemon=True)
        self.run_thread.start()

    def _cancel(self) -> None:
        if self.runner:
            self.runner.cancel()
            self.status_label.config(text="Останавливаю…")
            self._append_log("Отмена: потоки завершатся после текущего товара.")

    def _reset_tree(self, batches: List[List[str]]) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for index, batch in enumerate(batches, start=1):
            status = "Ожидает" if batch else "Пропущен (нет SKU)"
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(index, status, f"0/{len(batch)}", 0, "—", "—"),
            )

    # ------------------------------------------------------------ события

    def _pump_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(POLL_MS, self._pump_events)

    def _handle_event(self, event: Event) -> None:
        if event.kind is EventKind.LOG:
            self._append_log(event.message)
        elif event.kind is EventKind.THREAD_STARTED:
            self._set_cell(event.thread_id, "status", "Работает")
            self._append_log(event.message)
        elif event.kind is EventKind.SKU_DONE and event.result:
            self._on_sku_done(event)
        elif event.kind is EventKind.THREAD_DONE and event.cart:
            self._on_thread_done(event.cart)
        elif event.kind is EventKind.THREAD_FAILED:
            self._append_log(f"Поток упал: {event.message}")
        elif event.kind is EventKind.ALL_DONE:
            self._on_all_done(event.message)

    def _on_sku_done(self, event: Event) -> None:
        result = event.result
        assert result is not None
        self._done_count += 1
        self.progress.config(value=self._done_count)

        row = str(event.thread_id)
        if self.tree.exists(row):
            values = list(self.tree.item(row, "values"))
            done, total = values[2].split("/")
            fails = int(values[3])
            values[2] = f"{int(done) + (1 if result.ok else 0)}/{total}"
            values[3] = fails + (0 if result.ok else 1)
            self.tree.item(row, values=values)

        mark = "✓" if result.ok else "✗"
        self._append_log(
            f"{mark} Поток {event.thread_id} · {result.sku} · "
            f"{result.message} ({result.elapsed}s)"
        )

    def _on_thread_done(self, cart: CartResult) -> None:
        self.carts[cart.thread_id] = cart
        status = "Готово" if not cart.error else f"Ошибка: {cart.error}"
        row = str(cart.thread_id)
        if self.tree.exists(row):
            self.tree.item(
                row,
                values=(
                    cart.thread_id,
                    status,
                    f"{cart.added}/{cart.total}",
                    cart.failed,
                    f"{cart.elapsed}s",
                    cart.url,
                ),
            )
        in_cart = (
            f", в корзине позиций: {cart.items_in_cart}"
            if cart.items_in_cart >= 0
            else ""
        )
        self._append_log(
            f"Поток {cart.thread_id} завершён: {cart.added}/{cart.total} "
            f"за {cart.elapsed}s{in_cart}"
        )

    def _on_all_done(self, message: str) -> None:
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        added = sum(cart.added for cart in self.carts.values())
        total = sum(cart.total for cart in self.carts.values())
        self.status_label.config(text=f"{message}: {added}/{total}")
        self._append_log(f"{message}. Итого добавлено {added} из {total}.")

    # ------------------------------------------------------------ корзины

    def _selected_cart(self) -> CartResult | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Не выбрано", "Выберите поток в таблице.")
            return None
        cart = self.carts.get(int(selection[0]))
        if cart is None:
            messagebox.showinfo("Ещё нет", "Этот поток ещё не закончил сборку.")
        return cart

    def _copy_selected(self) -> None:
        cart = self._selected_cart()
        if cart is None:
            return
        self._to_clipboard(cart.url)
        self.status_label.config(text=f"Ссылка потока {cart.thread_id} скопирована")

    def _copy_all(self) -> None:
        if not self.carts:
            messagebox.showinfo("Пусто", "Корзины ещё не собраны.")
            return
        lines = [
            f"Поток {cart.thread_id} ({cart.added}/{cart.total}): {cart.url}"
            for cart in sorted(self.carts.values(), key=lambda c: c.thread_id)
        ]
        self._to_clipboard("\n".join(lines))
        self.status_label.config(text="Все ссылки скопированы")

    def _open_selected(self) -> None:
        cart = self._selected_cart()
        if cart is None:
            return
        if self.run_thread and self.run_thread.is_alive():
            messagebox.showwarning(
                "Сборка идёт",
                "Дождитесь конца сборки: профиль Chrome занят рабочим потоком.",
            )
            return
        try:
            driver = open_cart_in_browser(self.cfg, cart.thread_id)
            self.opened_browsers.append(driver)
            self._append_log(f"Открыл корзину потока {cart.thread_id} в браузере.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Не открылось", str(exc))

    def _to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()

    def _append_log(self, message: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    OzonCartApp(root)
    root.mainloop()
