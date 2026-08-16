/**
 * Режим А — основной.
 *
 * Берёт шаблон остатков, скачанный из личного кабинета Ozon Seller
 * (Управление логистикой → склад → Управление остатками → «Скачать в XLS»),
 * проставляет в него количества из вашей Google-таблицы и сохраняет
 * готовый файл, который остаётся только загрузить обратно в ЛК.
 *
 * Формат при этом остаётся ровно тот, который ждёт Ozon, — скрипт не
 * придумывает колонки, а заполняет уже существующие.
 */
function fillOzonTemplate() {
  var source = readSourceStocks_();
  var templateFolder = folderById_(CONFIG.TEMPLATE_FOLDER_ID, 'шаблон из ЛК');
  var outFolder = folderById_(CONFIG.OUTPUT_FOLDER_ID, 'готовые файлы');

  var templateFile = latestTemplateFile_(templateFolder);
  var tmpId = convertToSheet_(templateFile, 'tmp-ozon-' + stamp_());

  var result;
  try {
    result = applyStocks_(tmpId, source);
    var fileName = 'ozon-ostatki-' + stamp_() + '.xlsx';
    var out = exportXlsx_(tmpId, fileName, outFolder);
    result.fileName = fileName;
    result.fileUrl = out.getUrl();
    result.mode = 'Шаблон из ЛК';
    logRun_(result);
    mailResult_(out, result);
  } finally {
    trashQuietly_(tmpId);
  }

  tell_('Файл готов', report_(result));
  return result;
}

/** Самый свежий .xls/.xlsx в папке с шаблонами. */
function latestTemplateFile_(folder) {
  var files = folder.getFiles();
  var best = null;
  while (files.hasNext()) {
    var f = files.next();
    var name = f.getName().toLowerCase();
    if (name.indexOf('.xls') === -1) continue;
    if (name.indexOf('ozon-ostatki-') === 0) continue;   // это наш же результат
    if (!best || f.getLastUpdated() > best.getLastUpdated()) best = f;
  }
  if (!best) {
    throw new Error('В папке «' + folder.getName() +
      '» нет ни одного файла .xls/.xlsx. Положите туда шаблон, скачанный из ЛК Ozon.');
  }
  return best;
}

/**
 * Находит в конвертированном шаблоне лист с товарами и проставляет остатки.
 * @return {Object} статистика для отчёта.
 */
function applyStocks_(spreadsheetId, source) {
  var ss = SpreadsheetApp.openById(spreadsheetId);
  var sheets = ss.getSheets();
  var target = null;

  for (var s = 0; s < sheets.length; s++) {
    var found = locateColumns_(sheets[s]);
    if (found) { target = found; break; }
  }
  if (!target) {
    throw new Error('В шаблоне не найден лист с колонками артикула и количества. ' +
      'Откройте шаблон, посмотрите точные названия колонок и добавьте их ' +
      'в HEADER_ALIASES в файле Config.gs.');
  }

  var sheet = target.sheet;
  var firstDataRow = target.headerRow + 1;
  var lastRow = sheet.getLastRow();
  if (lastRow < firstDataRow) {
    throw new Error('В шаблоне нет строк с товарами.');
  }

  var height = lastRow - firstDataRow + 1;
  var skus = sheet.getRange(firstDataRow, target.skuCol + 1, height, 1).getValues();
  var qtyRange = sheet.getRange(firstDataRow, target.qtyCol + 1, height, 1);
  var qtys = qtyRange.getValues();

  var problems = source.problems.slice();
  var updated = 0, zeroed = 0, untouched = 0;
  var seen = {};

  for (var i = 0; i < height; i++) {
    var key = normKey_(skus[i][0]);
    if (!key) continue;
    seen[key] = true;

    if (Object.prototype.hasOwnProperty.call(source.map, key)) {
      qtys[i][0] = source.map[key];
      updated++;
    } else if (CONFIG.MISSING_SKU_ACTION === 'zero') {
      qtys[i][0] = 0;
      zeroed++;
    } else {
      untouched++;
    }
  }

  qtyRange.setValues(qtys);

  // Склад проставляем, только если колонка есть и пуста
  if (target.warehouseCol !== -1 && CONFIG.WAREHOUSE_NAME) {
    var whRange = sheet.getRange(firstDataRow, target.warehouseCol + 1, height, 1);
    var wh = whRange.getValues();
    var filled = false;
    for (var w = 0; w < height; w++) {
      if (normKey_(skus[w][0]) && !String(wh[w][0]).trim()) {
        wh[w][0] = CONFIG.WAREHOUSE_NAME;
        filled = true;
      }
    }
    if (filled) whRange.setValues(wh);
  }

  // Товары из таблицы, которых нет в шаблоне, — обычно опечатка в артикуле
  var missing = [];
  for (var m = 0; m < source.rows.length; m++) {
    if (!seen[source.rows[m].sku]) missing.push(source.rows[m].raw);
  }
  if (missing.length) {
    problems.push('Нет в шаблоне Ozon (' + missing.length + '): ' +
      missing.slice(0, 20).join(', ') + (missing.length > 20 ? ' …' : ''));
  }

  SpreadsheetApp.flush();

  return {
    updated: updated,
    zeroed: zeroed,
    untouched: untouched,
    notInTemplate: missing.length,
    sheetName: sheet.getName(),
    problems: problems
  };
}

/**
 * Ищет на листе строку заголовков и нужные колонки.
 * @return {?{sheet: Sheet, headerRow: number, skuCol: number,
 *            qtyCol: number, warehouseCol: number}}
 */
function locateColumns_(sheet) {
  var lastRow = Math.min(sheet.getLastRow(), 20);
  var lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return null;

  var head = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  for (var r = 0; r < head.length; r++) {
    var skuCol = matchColumn_(head[r], HEADER_ALIASES.sku);
    var qtyCol = matchColumn_(head[r], HEADER_ALIASES.qty);
    if (skuCol === -1 || qtyCol === -1) continue;
    return {
      sheet: sheet,
      headerRow: r + 1,                                   // 1-based
      skuCol: skuCol,
      qtyCol: qtyCol,
      warehouseCol: matchColumn_(head[r], HEADER_ALIASES.warehouse)
    };
  }
  return null;
}

/** Текст отчёта для всплывающего окна. */
function report_(result) {
  var lines = [
    'Файл: ' + result.fileName,
    '',
    'Проставлено остатков: ' + result.updated
  ];
  if (result.zeroed) lines.push('Обнулено (нет в таблице): ' + result.zeroed);
  if (result.untouched) lines.push('Оставлено без изменений: ' + result.untouched);
  if (result.notInTemplate) lines.push('SKU из таблицы не найдены в шаблоне: ' + result.notInTemplate);
  if (result.problems && result.problems.length) {
    lines.push('', 'Замечания:', result.problems.slice(0, 10).join('\n'));
  }
  lines.push('', 'Файл лежит в папке готовых файлов на Google Диске.',
    'Загрузите его в ЛК: Управление логистикой → склад →',
    'Управление остатками → загрузить файл → «Обновить остатки».');
  return lines.join('\n');
}
