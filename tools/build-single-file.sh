#!/usr/bin/env bash
# Собирает варианты для вставки в редактор Apps Script:
#
#   single-file/OzonOstatki.gs   — всё в одном файле (одна вставка при установке)
#   two-files/Настройки.gs       — только настройки
#   two-files/Скрипт.gs          — вся логика
#
# Вариант из двух файлов удобнее в работе: при обновлении заменяется только
# «Скрипт», а настройки с ID папок и списком магазинов остаются на месте.
#
# Запуск: bash tools/build-single-file.sh
set -euo pipefail

cd "$(dirname "$0")/.."

LOGIC="Utils Fill Build Menu"

emit_part() {                       # emit_part <имя файла проекта>
  printf '// ===================================================================\n'
  printf '// %s.gs\n' "$1"
  printf '// ===================================================================\n\n'
  cat "apps-script/$1.gs"
  printf '\n'
}

# --- всё в одном файле -------------------------------------------------
OUT=apps-script/single-file/OzonOstatki.gs
mkdir -p "$(dirname "$OUT")"
{
  cat <<'HEADER'
/**
 * Остатки Ozon и Wildberries из Google-таблицы — всё в одном файле.
 *
 * ЭТОТ ФАЙЛ СОБИРАЕТСЯ АВТОМАТИЧЕСКИ — не правьте его в репозитории,
 * правьте исходники в apps-script/ и запускайте tools/build-single-file.sh.
 *
 * Что делать после вставки в Apps Script:
 *   1. Заполнить OUTPUT_FOLDER_ID и SHOPS ниже.
 *   2. Слева «Сервисы» → + → Drive API → версия v3 → Добавить.
 *   3. Сохранить (Ctrl+S), вернуться в таблицу и перезагрузить страницу.
 *
 * При обновлении кода настройки в этом файле затираются. Чтобы этого не
 * происходило, есть вариант из двух файлов — apps-script/two-files/.
 */

HEADER
  for f in Config $LOGIC; do emit_part "$f"; done
} > "$OUT"
echo "Собрано: $OUT ($(wc -l < "$OUT") строк)"

# --- два файла: настройки отдельно от логики ---------------------------
mkdir -p apps-script/two-files

{
  cat <<'HEADER'
/**
 * Настройки. Этот файл правите вы — при обновлении кода он не меняется.
 *
 * Обновление: заменить содержимое файла «Скрипт», этот оставить как есть.
 */

HEADER
  cat apps-script/Config.gs
} > 'apps-script/two-files/Настройки.gs'

{
  cat <<'HEADER'
/**
 * Логика. СОБИРАЕТСЯ АВТОМАТИЧЕСКИ — при обновлении заменяйте этот файл
 * целиком, настройки лежат отдельно, в файле «Настройки».
 *
 * Правьте исходники в apps-script/ и запускайте tools/build-single-file.sh.
 */

HEADER
  for f in $LOGIC; do emit_part "$f"; done
} > 'apps-script/two-files/Скрипт.gs'

echo "Собрано: apps-script/two-files/Настройки.gs ($(wc -l < 'apps-script/two-files/Настройки.gs') строк)"
echo "Собрано: apps-script/two-files/Скрипт.gs ($(wc -l < 'apps-script/two-files/Скрипт.gs') строк)"
