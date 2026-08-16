/**
 * Вспомогательные функции: нормализация значений, поиск колонок,
 * чтение исходного листа, выгрузка XLSX, логирование.
 */

/** Приводит значение ячейки к строке-ключу для сравнения артикулов. */
function normKey_(v) {
  if (v === null || v === undefined) return '';
  var s;
  if (typeof v === 'number') {
    // 12345 не должен превратиться в "12345.0" или "1.2345e+4"
    s = (Math.abs(v % 1) < 1e-9) ? v.toFixed(0) : String(v);
  } else {
    s = String(v);
  }
  return s.replace(/\u00a0/g, ' ').trim().replace(/\s+/g, ' ').toLowerCase();
}

/** Приводит заголовок колонки к сравнимому виду. */
function normHeader_(v) {
  return String(v === null || v === undefined ? '' : v)
    .replace(/\u00a0/g, ' ')
    .replace(/[*:]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

/**
 * Ищет в строке заголовков колонку по списку допустимых названий.
 *
 * Названия перебираются в порядке приоритета, а не в порядке колонок: если
 * в шаблоне есть и «Артикул», и «Баркод», для Wildberries выберется баркод,
 * потому что для него он стоит в списке первым.
 *
 * Сначала точные совпадения, затем — заголовки, начинающиеся с названия
 * (из нескольких подходящих берётся самый короткий, чтобы «Количество»
 * выигрывало у «Количество в упаковке»).
 * @return {number} индекс колонки или -1.
 */
function matchColumn_(headerCells, aliases) {
  var norm = headerCells.map(normHeader_);
  var i, a;

  for (a = 0; a < aliases.length; a++) {
    for (i = 0; i < norm.length; i++) {
      if (norm[i] && norm[i] === aliases[a]) return i;
    }
  }

  for (a = 0; a < aliases.length; a++) {
    var best = -1;
    for (i = 0; i < norm.length; i++) {
      if (norm[i] && norm[i].indexOf(aliases[a]) === 0) {
        if (best === -1 || norm[i].length < norm[best].length) best = i;
      }
    }
    if (best !== -1) return best;
  }
  return -1;
}

/**
 * Названия колонки с кодом товара для площадки магазина.
 * Ozon — артикул продавца, Wildberries — баркод.
 */
function idAliasesFor_(shop) {
  var list = (shop && shop.platform === 'wb')
    ? HEADER_ALIASES.barcode.concat(HEADER_ALIASES.sku)
    : HEADER_ALIASES.sku.concat(HEADER_ALIASES.barcode);

  if (shop && shop.idHeader) {
    var own = normHeader_(shop.idHeader);
    if (own) list = [own].concat(list.filter(function (a) { return a !== own; }));
  }
  return list;
}

/** То же для вашего листа: плюс заголовок из общих настроек, но пониже. */
function sourceIdAliases_(shop) {
  var list = idAliasesFor_(shop);
  var own = normHeader_(CONFIG.SKU_HEADER);
  return (own && list.indexOf(own) === -1) ? list.concat([own]) : list;
}

/** Список названий колонки с учётом значения из CONFIG. */
function aliasesFor_(configHeader, defaults) {
  var own = normHeader_(configHeader);
  if (!own) return defaults;
  return [own].concat(defaults.filter(function (a) { return a !== own; }));
}

/** Число или null, если значение не похоже на количество. */
function parseQty_(v) {
  if (v === null || v === undefined || v === '') return null;
  if (typeof v === 'number') return Math.round(v);
  var s = String(v).replace(/\u00a0/g, '').replace(/\s/g, '').replace(',', '.');
  if (!/^-?\d+(\.\d+)?$/.test(s)) return null;
  return Math.round(parseFloat(s));
}

/**
 * Читает лист с остатками.
 * @param {Object=} shop магазин; без него — общие настройки.
 * @return {{map: Object, rows: Array, problems: Array}}
 */
function readSourceStocks_(shop) {
  var name = (shop && shop.sheet) || CONFIG.SOURCE_SHEET;
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name);
  if (!sh) {
    throw new Error('Не найден лист «' + name +
      '». Проверьте название листа в настройках (Config.gs).');
  }

  var values = sh.getDataRange().getValues();
  var skuAliases = sourceIdAliases_(shop);
  var qtyAliases = aliasesFor_(CONFIG.QTY_HEADER, HEADER_ALIASES.qty);

  var headerRow = -1, skuCol = -1, qtyCol = -1;
  for (var r = 0; r < Math.min(values.length, 10); r++) {
    var s = matchColumn_(values[r], skuAliases);
    var q = matchColumn_(values[r], qtyAliases);
    if (s !== -1 && q !== -1) { headerRow = r; skuCol = s; qtyCol = q; break; }
  }
  if (headerRow === -1) {
    throw new Error('На листе «' + name + '» не найдены колонка с кодом товара (' +
      ((shop && shop.platform === 'wb') ? 'баркод' : 'артикул') +
      ') и колонка «' + CONFIG.QTY_HEADER +
      '». Заголовки должны быть в одной из первых 10 строк.');
  }

  // Название товара — необязательно, Ozon его не требует
  var nameCol = matchColumn_(values[headerRow],
    aliasesFor_(CONFIG.NAME_HEADER, HEADER_ALIASES.name));

  var map = {};
  var rows = [];
  var problems = [];

  for (var i = headerRow + 1; i < values.length; i++) {
    var rawSku = values[i][skuCol];
    var rawQty = values[i][qtyCol];
    var sku = normKey_(rawSku);
    if (!sku) continue;                         // пустая строка — пропускаем молча

    var qty = parseQty_(rawQty);
    if (qty === null) {
      problems.push('Строка ' + (i + 1) + ': у SKU «' + rawSku +
        '» некорректное количество («' + rawQty + '»), строка пропущена.');
      continue;
    }
    if (qty < 0) {
      problems.push('Строка ' + (i + 1) + ': у SKU «' + rawSku +
        '» отрицательное количество, взят 0.');
      qty = 0;
    }
    if (Object.prototype.hasOwnProperty.call(map, sku)) {
      problems.push('SKU «' + rawSku + '» встречается несколько раз, ' +
        'взято последнее значение (' + qty + ').');
    }

    map[sku] = qty;
    rows.push({
      sku: sku,
      raw: rawSku,
      qty: qty,
      name: nameCol === -1 ? '' : String(values[i][nameCol] || '').trim(),
      row: i + 1
    });
  }

  if (!rows.length) {
    throw new Error('На листе «' + name + '» нет ни одной строки с данными.');
  }
  return { map: map, rows: rows, problems: problems };
}

/** Папка Диска по ID с понятной ошибкой, если ID не задан или неверен. */
function folderById_(id, whatFor) {
  if (!id) {
    throw new Error('Не заполнен ID папки для «' + whatFor + '» в Config.gs.');
  }
  try {
    return DriveApp.getFolderById(id);
  } catch (e) {
    throw new Error('Не удаётся открыть папку «' + whatFor + '» (ID: ' + id +
      '). Проверьте ID и доступ к папке.');
  }
}

/** Копирует файл на Диске, конвертируя его в Google Таблицу. */
function convertToSheet_(file, name) {
  try {
    var copy = Drive.Files.copy(
      { name: name, mimeType: MimeType.GOOGLE_SHEETS },
      file.getId(),
      { supportsAllDrives: true }
    );
    return copy.id;
  } catch (e) {
    // Запасной вариант на случай, если подключена Drive API v2
    var copy2 = Drive.Files.copy(
      { title: name, mimeType: MimeType.GOOGLE_SHEETS },
      file.getId()
    );
    return copy2.id;
  }
}

/** Выгружает Google Таблицу в .xlsx и сохраняет файл в папку. */
function exportXlsx_(spreadsheetId, fileName, folder) {
  var url = 'https://www.googleapis.com/drive/v3/files/' + spreadsheetId +
    '/export?mimeType=application%2Fvnd.openxmlformats-officedocument.spreadsheetml.sheet';
  var res = UrlFetchApp.fetch(url, {
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) {
    throw new Error('Не удалось выгрузить XLSX (код ' + res.getResponseCode() + '): ' +
      res.getContentText().slice(0, 300));
  }
  return folder.createFile(res.getBlob().setName(fileName));
}

/** Удаляет временную таблицу, не роняя выполнение при ошибке. */
function trashQuietly_(fileId) {
  try {
    DriveApp.getFileById(fileId).setTrashed(true);
  } catch (e) {
    Logger.log('Не удалось удалить временный файл ' + fileId + ': ' + e.message);
  }
}

/** Дата для имени файла: 2026-08-16_0805 */
function stamp_() {
  return Utilities.formatDate(new Date(),
    Session.getScriptTimeZone(), 'yyyy-MM-dd_HHmm');
}

/** Пишет строку в лист «Лог». */
function logRun_(result) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(LOG_SHEET);
  if (!sh) {
    sh = ss.insertSheet(LOG_SHEET);
    sh.appendRow(['Дата', 'Магазин', 'Режим', 'Файл', 'Строк в файле',
      'Дописано', 'Обнулено', 'Склад', 'Замечания']);
    sh.setFrozenRows(1);
  }
  sh.appendRow([
    new Date(),
    result.shop || '',
    result.mode,
    result.fileUrl ? '=HYPERLINK("' + result.fileUrl + '";"' + result.fileName + '")' : '',
    result.updated || 0,
    result.added || 0,
    result.zeroed || 0,
    result.warehouse || '',
    (result.problems || []).join('\n')
  ]);
}

/** Показывает сообщение, если скрипт запущен вручную из таблицы. */
function tell_(title, message) {
  try {
    SpreadsheetApp.getUi().alert(title, message, SpreadsheetApp.getUi().ButtonSet.OK);
  } catch (e) {
    Logger.log(title + '\n' + message);   // запуск по триггеру — UI недоступен
  }
}

/** Превращает название магазина в кусок имени файла. */
function slug_(name) {
  return String(name || '').trim()
    .replace(/[^0-9A-Za-zА-Яа-яЁё_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

/** Отправляет готовые файлы на почту одним письмом, если указан адрес. */
function mailResults_(results, errors) {
  if (!CONFIG.EMAIL_TO) return;

  var lines = ['Файлы остатков для загрузки в Ozon Seller готовы.', ''];
  var attachments = [];

  for (var i = 0; i < results.length; i++) {
    var r = results[i];
    lines.push((r.shop ? r.shop + ' — ' : '') + r.fileName);
    lines.push('  строк: ' + (r.updated || 0) + ', склад: ' + (r.warehouse || '—'));
    if (r.problems && r.problems.length) {
      lines.push('  замечания: ' + r.problems.join('; '));
    }
    lines.push('  ' + r.fileUrl, '');
    if (r.file) attachments.push(r.file.getBlob());
  }

  if (errors && errors.length) {
    lines.push('НЕ УДАЛОСЬ:', errors.join('\n'));
  }

  MailApp.sendEmail({
    to: CONFIG.EMAIL_TO,
    subject: 'Остатки Ozon FBS — ' + results.length + ' файл(ов)' +
      (errors && errors.length ? ', есть ошибки' : ''),
    body: lines.join('\n'),
    attachments: attachments
  });
}

/**
 * Список магазинов. Если CONFIG.SHOPS пуст — один магазин из общих настроек.
 */
function shopsList_() {
  var raw = CONFIG.SHOPS || [];
  var list = [];

  for (var i = 0; i < raw.length; i++) {
    if (!raw[i] || !raw[i].sheet) continue;
    list.push({
      name: raw[i].name || raw[i].sheet,
      sheet: raw[i].sheet,
      templateFolderId: raw[i].templateFolderId || CONFIG.TEMPLATE_FOLDER_ID,
      outputFolderId: raw[i].outputFolderId || CONFIG.OUTPUT_FOLDER_ID,
      warehouse: raw[i].warehouse || '',
      platform: raw[i].platform === 'wb' ? 'wb' : 'ozon',
      idHeader: raw[i].idHeader || ''
    });
  }

  if (!list.length) {
    list.push({
      name: '',
      sheet: CONFIG.SOURCE_SHEET,
      templateFolderId: CONFIG.TEMPLATE_FOLDER_ID,
      outputFolderId: CONFIG.OUTPUT_FOLDER_ID,
      warehouse: CONFIG.WAREHOUSE_NAME,
      platform: 'ozon',
      idHeader: ''
    });
  }
  return list;
}

/**
 * У каждого кабинета свой шаблон со своим списком складов. Общая папка на
 * несколько магазинов означала бы, что все файлы уедут на склад первого,
 * — это молча испортило бы остатки, поэтому останавливаемся сразу.
 */
function assertDistinctTemplates_(shops) {
  if (shops.length < 2) return;
  var seen = {};
  for (var i = 0; i < shops.length; i++) {
    var id = shops[i].templateFolderId;
    if (!id) {
      throw new Error('У магазина «' + shops[i].name +
        '» не указана папка с шаблоном (templateFolderId).');
    }
    if (seen[id]) {
      throw new Error('Магазины «' + seen[id] + '» и «' + shops[i].name +
        '» указывают на одну папку с шаблоном. У каждого кабинета должен быть ' +
        'свой шаблон — иначе остатки уедут не на тот склад.');
    }
    seen[id] = shops[i].name;
  }
}
