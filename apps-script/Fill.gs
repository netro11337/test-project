/**
 * Режим А — основной.
 *
 * Берёт шаблон остатков, скачанный из личного кабинета Ozon Seller
 * (Управление логистикой → склад → Управление остатками → «Скачать в XLS»),
 * заполняет его данными из вашей Google-таблицы и сохраняет готовый файл,
 * который остаётся только загрузить обратно в ЛК.
 *
 * Шаблон приходит пустым: строка 1 — заголовки, ниже одна-две служебные
 * строки с подсказками («Редактируемое обязательное», «Укажите артикул…»),
 * а данные начинаются с первой пустой строки. Скрипт находит эту границу
 * сам и служебные строки не трогает.
 *
 * Магазинов может быть несколько: тогда за один запуск получается по файлу
 * на каждый кабинет — см. CONFIG.SHOPS.
 */
function fillOzonTemplate() {
  var shops = shopsList_();
  assertDistinctTemplates_(shops);

  var results = [];
  var errors = [];

  for (var i = 0; i < shops.length; i++) {
    try {
      var r = fillOneShop_(shops[i]);
      results.push(r);
      logRun_(r);
    } catch (e) {
      // Один магазин не должен ронять остальные
      var where = shops[i].name ? shops[i].name + ': ' : '';
      errors.push(where + e.message);
      logRun_({
        shop: shops[i].name,
        mode: 'Ошибка',
        problems: [e.message]
      });
    }
  }

  mailResults_(results, errors);
  tell_(results.length ? 'Готово' : 'Не получилось', report_(results, errors));

  if (!results.length) {
    throw new Error(errors.join('\n'));   // чтобы автозапуск увидел сбой
  }
  return results;
}

/** Готовит файл для одного магазина. */
function fillOneShop_(shop) {
  var source = readSourceStocks_(shop.sheet);
  var templateFolder = folderById_(shop.templateFolderId,
    'шаблон' + (shop.name ? ' магазина ' + shop.name : ' из ЛК'));
  var outFolder = folderById_(shop.outputFolderId, 'готовые файлы');

  var templateFile = latestTemplateFile_(templateFolder);
  var tmpId = convertToSheet_(templateFile, 'tmp-ozon-' + stamp_());

  try {
    var result = applyStocks_(tmpId, source, shop);
    var fileName = 'ozon-ostatki-' +
      (shop.name ? slug_(shop.name) + '-' : '') + stamp_() + '.xlsx';
    var out = exportXlsx_(tmpId, fileName, outFolder);

    result.shop = shop.name;
    result.mode = 'Шаблон из ЛК';
    result.fileName = fileName;
    result.fileUrl = out.getUrl();
    result.file = out;
    return result;
  } finally {
    trashQuietly_(tmpId);
  }
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
 * Находит в конвертированном шаблоне лист с товарами и заполняет его.
 * Строки, которые уже есть в шаблоне, обновляются на месте; всё остальное
 * из таблицы дописывается ниже.
 * @return {Object} статистика для отчёта.
 */
function applyStocks_(spreadsheetId, source, shop) {
  var ss = SpreadsheetApp.openById(spreadsheetId);
  var sheets = ss.getSheets();
  var loc = null;

  for (var s = 0; s < sheets.length; s++) {
    loc = locateColumns_(sheets[s]);
    if (loc) break;
  }
  if (!loc) {
    throw new Error('В шаблоне не найден лист с колонками артикула и количества. ' +
      'Откройте шаблон, посмотрите точные названия колонок и добавьте их ' +
      'в HEADER_ALIASES в файле Config.gs.');
  }

  var sheet = loc.sheet;
  var lastCol = sheet.getLastColumn();
  var dataStart = findDataStart_(sheet, loc);
  var warehouse = resolveWarehouse_(sheet, loc, dataStart, shop);
  var problems = source.problems.slice();

  // Уже заполненные строки шаблона (в пустом шаблоне их нет)
  var existing = [];
  if (sheet.getLastRow() >= dataStart) {
    existing = sheet.getRange(dataStart, 1,
      sheet.getLastRow() - dataStart + 1, lastCol).getValues();
  }

  var updated = 0, zeroed = 0, untouched = 0;
  var seen = {};

  for (var i = 0; i < existing.length; i++) {
    var key = normKey_(existing[i][loc.skuCol]);
    if (!key) continue;
    seen[key] = true;

    if (Object.prototype.hasOwnProperty.call(source.map, key)) {
      existing[i][loc.qtyCol] = source.map[key];
      updated++;
    } else if (CONFIG.MISSING_SKU_ACTION === 'zero') {
      existing[i][loc.qtyCol] = 0;
      zeroed++;
    } else {
      untouched++;
    }
    if (loc.warehouseCol !== -1 && !String(existing[i][loc.warehouseCol]).trim()) {
      existing[i][loc.warehouseCol] = warehouse;
    }
  }

  // Всё, чего в шаблоне ещё не было, дописываем ниже
  var added = 0;
  for (var r = 0; r < source.rows.length; r++) {
    var item = source.rows[r];
    if (seen[item.sku]) continue;

    var row = new Array(lastCol);
    for (var c = 0; c < lastCol; c++) row[c] = '';
    row[loc.skuCol] = item.raw;
    row[loc.qtyCol] = item.qty;
    if (loc.warehouseCol !== -1) row[loc.warehouseCol] = warehouse;
    if (loc.nameCol !== -1 && item.name) row[loc.nameCol] = item.name;

    existing.push(row);
    added++;
  }

  if (!existing.length) {
    throw new Error('Нечего записывать: в таблице нет ни одной строки с остатками.');
  }

  // На листе может не хватать строк под наши данные
  var needRows = dataStart + existing.length - 1;
  if (needRows > sheet.getMaxRows()) {
    sheet.insertRowsAfter(sheet.getMaxRows(), needRows - sheet.getMaxRows());
  }

  sheet.getRange(dataStart, 1, existing.length, lastCol).setValues(existing);
  SpreadsheetApp.flush();

  return {
    updated: updated + added,
    added: added,
    zeroed: zeroed,
    untouched: untouched,
    warehouse: warehouse,
    sheetName: sheet.getName(),
    problems: problems
  };
}

/**
 * Ищет на листе строку заголовков и нужные колонки.
 * @return {?{sheet: Sheet, headerRow: number, skuCol: number, qtyCol: number,
 *            warehouseCol: number, nameCol: number}}
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
      warehouseCol: matchColumn_(head[r], HEADER_ALIASES.warehouse),
      nameCol: matchColumn_(head[r], HEADER_ALIASES.name)
    };
  }
  return null;
}

/**
 * Первая строка под заголовком, куда можно писать данные: служебные строки
 * с подсказками Ozon пропускаются.
 */
function findDataStart_(sheet, loc) {
  var lastCol = sheet.getLastColumn();
  var maxScan = Math.min(sheet.getLastRow(), loc.headerRow + 10);

  for (var r = loc.headerRow + 1; r <= maxScan; r++) {
    var row = sheet.getRange(r, 1, 1, lastCol).getValues()[0];

    var empty = true;
    for (var c = 0; c < row.length; c++) {
      if (String(row[c]).trim() !== '') { empty = false; break; }
    }
    if (empty) return r;

    // Настоящая строка с товаром: есть артикул и числовое количество
    if (normKey_(row[loc.skuCol]) && parseQty_(row[loc.qtyCol]) !== null) return r;

    if (!isServiceRow_(row)) {
      // Незнакомая непустая строка — на всякий случай не затираем её
      continue;
    }
  }
  return maxScan + 1;
}

/** Похожа ли строка на подсказку Ozon («Редактируемое обязательное» и т.п.). */
function isServiceRow_(row) {
  for (var c = 0; c < row.length; c++) {
    var v = normHeader_(row[c]);
    if (!v) continue;
    for (var m = 0; m < SERVICE_ROW_MARKERS.length; m++) {
      if (v.indexOf(SERVICE_ROW_MARKERS[m]) === 0) return true;
    }
  }
  return false;
}

/**
 * Определяет название склада: из настроек либо из выпадающего списка,
 * который Ozon кладёт в колонку склада.
 */
function resolveWarehouse_(sheet, loc, dataStart, shop) {
  if (loc.warehouseCol === -1) return '';

  var wanted = (shop && shop.warehouse) || CONFIG.WAREHOUSE_NAME || '';
  var where = shop && shop.name ? ' (магазин ' + shop.name + ')' : '';
  var options = warehouseOptions_(sheet, loc, dataStart);

  if (wanted) {
    if (!options.length) return wanted;         // списка нет — верим настройке
    var picked = matchWarehouse_(wanted, options);
    if (picked.length === 1) return picked[0];
    if (picked.length > 1) {
      throw new Error('Под «' + wanted + '» подходит несколько складов' + where +
        ': ' + picked.join(' | ') + '. Уточните название.');
    }
    throw new Error('Склад «' + wanted + '» не найден в шаблоне' + where +
      '. Доступные варианты: ' + options.join(' | '));
  }

  if (options.length === 1) return options[0];
  if (options.length > 1) {
    throw new Error('В шаблоне несколько складов' + where + ': ' +
      options.join(' | ') + '. Укажите нужный в настройках.');
  }
  throw new Error('Не удалось определить склад' + where +
    ': в шаблоне нет выпадающего списка. Впишите название склада в настройки ' +
    'ровно как в личном кабинете.');
}

/**
 * Подбирает склад по неполному названию. В шаблоне склад записан как
 * «Название (идентификатор)», поэтому цифры знать не нужно — достаточно
 * названия или его узнаваемой части.
 */
function matchWarehouse_(wanted, options) {
  var w = normHeader_(wanted);
  var i, hits = [];

  for (i = 0; i < options.length; i++) {
    if (normHeader_(options[i]) === w) return [options[i]];
  }
  for (i = 0; i < options.length; i++) {
    if (normHeader_(options[i]).indexOf(w) === 0) hits.push(options[i]);
  }
  if (hits.length) return hits;

  for (i = 0; i < options.length; i++) {
    if (normHeader_(options[i]).indexOf(w) !== -1) hits.push(options[i]);
  }
  return hits;
}

/** Значения выпадающего списка складов, если он есть в шаблоне. */
function warehouseOptions_(sheet, loc, dataStart) {
  var probeRows = [dataStart, dataStart + 1, loc.headerRow + 1];
  for (var i = 0; i < probeRows.length; i++) {
    var row = probeRows[i];
    if (row < 1 || row > sheet.getMaxRows()) continue;

    var rule = sheet.getRange(row, loc.warehouseCol + 1).getDataValidation();
    if (!rule) continue;

    var type = rule.getCriteriaType();
    var values = rule.getCriteriaValues();

    if (type === SpreadsheetApp.DataValidationCriteria.VALUE_IN_LIST) {
      return (values[0] || []).map(function (v) { return String(v).trim(); })
        .filter(function (v) { return v !== ''; });
    }
    if (type === SpreadsheetApp.DataValidationCriteria.VALUE_IN_RANGE) {
      var listed = values[0].getValues();
      var out = [];
      for (var k = 0; k < listed.length; k++) {
        var v = String(listed[k][0]).trim();
        if (v) out.push(v);
      }
      return out;
    }
  }
  return [];
}

/** Текст отчёта для всплывающего окна. */
function report_(results, errors) {
  var lines = [];

  for (var i = 0; i < results.length; i++) {
    var r = results[i];
    if (r.shop) lines.push('— ' + r.shop + ' —');
    lines.push('Файл: ' + r.fileName);
    lines.push('Строк с остатками: ' + r.updated);
    if (r.added && r.added !== r.updated) lines.push('Дописано: ' + r.added);
    if (r.zeroed) lines.push('Обнулено (нет в таблице): ' + r.zeroed);
    if (r.untouched) lines.push('Оставлено без изменений: ' + r.untouched);
    if (r.warehouse) lines.push('Склад: ' + r.warehouse);
    if (r.problems && r.problems.length) {
      lines.push('Замечания:', r.problems.slice(0, 10).join('\n'));
    }
    lines.push('');
  }

  if (errors && errors.length) {
    lines.push('НЕ ПОЛУЧИЛОСЬ:', errors.join('\n'), '');
  }

  if (results.length) {
    lines.push('Файлы лежат в папке готовых файлов на Google Диске.',
      'Загрузите каждый в свой кабинет: Управление логистикой → склад →',
      'Управление остатками → загрузить файл → «Обновить остатки».');
  }
  return lines.join('\n');
}
