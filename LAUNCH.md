# 🚀 Запуск Софта В Два Клика

## Windows (Самый простой способ)

### Вариант 1: Прямой запуск (РЕКОМЕНДУЕТСЯ)

1. **Распакуйте архив** - распакуйте папку где угодно
2. **Дважды кликните** на файл:
   ```
   install_and_run.bat
   ```
3. **Ждите** - система установит всё необходимое
4. **Готово** - откроется приложение!

### Вариант 2: Через Python

1. **Убедитесь что установлен Python 3.8+** (https://python.org)
2. **Дважды кликните** на файл:
   ```
   start.py
   ```
3. **Система установит всё** и запустит приложение

### Вариант 3: Создать ярлык на рабочий стол

1. **Правый клик** на `install_and_run.bat`
2. **"Отправить"** → **"Рабочий стол (создать ярлык)"**
3. **Переименуйте** ярлык на "Озон Авторегистрация" (опционально)
4. Теперь можно запускать с рабочего стола двойным кликом!

---

## Linux / macOS

### Способ 1: Запустить скрипт

```bash
# Откройте терминал в папке с проектом и выполните:
bash install_and_run.sh

# Или просто:
./install_and_run.sh
```

### Способ 2: Через Python

```bash
python3 start.py
```

### Способ 3: Вручную (пошагово)

```bash
# Установить зависимости
pip3 install -r requirements.txt

# Установить браузер
playwright install chromium

# Запустить приложение
python3 ozon_ui_panel.py
```

---

## 🎯 Что происходит при запуске

```
1. Проверка Python 3.8+
   ↓
2. Установка зависимостей (requests, faker, playwright, pyyaml)
   ↓
3. Установка браузера Chromium
   ↓
4. Запуск UI приложения
   ↓
5. Готово к использованию!
```

---

## ⚠️ Если что-то не работает

### Ошибка: "Python не найден"
- Установите Python 3.8+ с https://python.org
- **Важно**: При установке отметьте "Add Python to PATH"
- Перезагрузитесь после установки

### Ошибка: "pip не найден"
```bash
# Windows
python -m pip install --upgrade pip

# Linux/macOS
python3 -m pip install --upgrade pip
```

### Ошибка: "Не установлены зависимости"
```bash
# Windows
pip install -r requirements.txt

# Linux/macOS
pip3 install -r requirements.txt
```

### Ошибка: "Не установлен Chromium"
```bash
# Windows
python -m playwright install chromium

# Linux/macOS
python3 -m playwright install chromium
```

### Приложение не открывается
1. Убедитесь что установлен Python 3.8+
2. Убедитесь что установлены все зависимости
3. Попробуйте запустить вручную:
   ```bash
   # Windows
   python ozon_ui_panel.py
   
   # Linux/macOS
   python3 ozon_ui_panel.py
   ```

---

## 📝 Первый запуск

1. **Нажмите на кнопку** "Проверить баланс MegaSMS"
2. **Подготовьте список email** в формате:
   ```
   email@gmail.com:password123
   user@mail.ru:password456
   ```
3. **Загрузите список** или вставьте вручную
4. **Укажите количество** аккаунтов
5. **Нажмите "Начать"**
6. **Смотрите логи** в левой части
7. **Результаты** появляются в правой части

---

## 🔄 Если запуск не работает

### Полная переустановка (Windows)

```batch
@echo off
REM Удалить старые зависимости
pip uninstall -y playwright faker requests pyyaml

REM Удалить кэш Python
rmdir /s /q __pycache__

REM Переустановить всё
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium

REM Запустить
python ozon_ui_panel.py
```

### Полная переустановка (Linux/macOS)

```bash
# Удалить старые зависимости
pip3 uninstall -y playwright faker requests pyyaml

# Удалить кэш Python
rm -rf __pycache__

# Переустановить всё
pip3 install --upgrade pip
pip3 install -r requirements.txt
python3 -m playwright install chromium

# Запустить
python3 ozon_ui_panel.py
```

---

## 💡 Советы

### Для удобства создайте файл emails.txt:
```
email1@gmail.com:password123
email2@mail.ru:password456
email3@yandex.com:password789
```

Потом в приложении нажмите "Загрузить из файла" и выберите этот файл.

### Сохраняйте результаты:
После завершения нажмите "Сохранить в файл" в правой панели и выберите где сохранить.

### Копируйте результаты:
Нажмите "Копировать результаты" и вставьте в нужное место (Ctrl+V).

---

## 📋 Системные требования

- **ОС**: Windows 7+, macOS 10.12+, Ubuntu 16.04+
- **Python**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Память**: минимум 512 МБ
- **Диск**: минимум 1 ГБ (для Chromium)
- **Интернет**: постоянное подключение

---

## 🎬 Видео инструкция (если нужна)

Процесс:
1. Скачиваете архив
2. Распаковываете папку
3. Открываете папку
4. Двойной клик на `install_and_run.bat` (Windows) или `start.py` (любая ОС)
5. Ждите установки (~5-10 минут)
6. Используете приложение!

---

## ✅ Чек-лист перед первым запуском

- [ ] Python 3.8+ установлен (проверьте: `python --version`)
- [ ] Интернет работает
- [ ] Архив распакован в отдельную папку
- [ ] В папке есть файл `install_and_run.bat` или `start.py`
- [ ] Готов список email адресов (email:пароль)

Если всё отмечено - запускайте `install_and_run.bat` или `start.py` и наслаждайтесь! 🚀

---

**Версия**: 2.0
**Последнее обновление**: 2024
**Состояние**: Готов к использованию
