#!/usr/bin/env bash
# Собирает все файлы проекта в один OzonOstatki.gs — чтобы вставить
# в редактор Apps Script одной вставкой, а не пятью.
#
# Запуск: bash tools/build-single-file.sh
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=apps-script/single-file/OzonOstatki.gs
mkdir -p "$(dirname "$OUT")"

{
  cat <<'HEADER'
/**
 * Остатки Ozon FBS из Google-таблицы — всё в одном файле.
 *
 * ЭТОТ ФАЙЛ СОБИРАЕТСЯ АВТОМАТИЧЕСКИ — не правьте его в репозитории,
 * правьте исходники в apps-script/ и запускайте tools/build-single-file.sh.
 *
 * Что делать после вставки в Apps Script:
 *   1. Заполнить TEMPLATE_FOLDER_ID и OUTPUT_FOLDER_ID ниже.
 *   2. Слева «Сервисы» → + → Drive API → версия v3 → Добавить.
 *   3. Сохранить (Ctrl+S), вернуться в таблицу и перезагрузить страницу.
 */

HEADER

  for f in Config Utils Fill Build Menu; do
    printf '// ===================================================================\n'
    printf '// %s.gs\n' "$f"
    printf '// ===================================================================\n\n'
    cat "apps-script/$f.gs"
    printf '\n'
  done
} > "$OUT"

echo "Собрано: $OUT ($(wc -l < "$OUT") строк)"
