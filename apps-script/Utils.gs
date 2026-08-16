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
 * Сначала точное совпадение, затем — заголовок, начинающийся с алиаса
 * (из нескольких подходящих берётся самый короткий, чтобы «Количество»
 * выигрывало у «Количество в упаковке»).
 * @return {number} индекс колонки или -1.
 */
function matchColumn_(headerCells, aliases) {
  var norm = headerCells.map(normHeader_);
  var i, j, k;

  for (i = 0; i < norm.length; i++) {
    if (norm[i] && aliases.indexOf(norm[i]) !== -1) return i;
  }

  var best = -1;
  for (j = 0; j < norm.length; j++) {
    if (!norm[j]) continue;
    for (k = 0; k < aliases.length; k++) {
      if (norm[j].indexOf(aliases[k]) === 0) {
        if (best === -1 || norm[j].length < norm[best].length) best = j;
        break;
      }
    }
  }
  return best;
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
 * @return {{map: Object, rows: Array, problems: Array}}
 */
function readSourceStocks_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(CONFIG.SOURCE_SHEET);
  if (!sh) {
    throw new Error('Не найден лист «' + CONFIG.SOURCE_SHEET +
      '». Проверьте CONFIG.SOURCE_SHEET в файле Config.gs.');
  }

  var values = sh.getDataRange().getValues();
  var skuAliases = aliasesFor_(CONFIG.SKU_HEADER, HEADER_ALIASES.sku);
  var qtyAliases = aliasesFor_(CONFIG.QTY_HEADER, HEADER_ALIASES.qty);

  var headerRow = -1, skuCol = -1, qtyCol = -1;
  for (var r = 0; r < Math.min(values.length, 10); r++) {
    var s = matchColumn_(values[r], skuAliases);
    var q = matchColumn_(values[r], qtyAliases);
    if (s !== -1 && q !== -1) { headerRow = r; skuCol = s; qtyCol = q; break; }
  }
  if (headerRow === -1) {
    throw new Error('На листе «' + CONFIG.SOURCE_SHEET + '» не найдены колонки «' +
      CONFIG.SKU_HEADER + '» и «' + CONFIG.QTY_HEADER +
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
    throw new Error('На листе «' + CONFIG.SOURCE_SHEET + '» нет ни одной строки с данными.');
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
    sh.appendRow(['Дата', 'Режим', 'Файл', 'Строк в файле',
      'Дописано', 'Обнулено', 'Склад', 'Замечания']);
    sh.setFrozenRows(1);
  }
  sh.appendRow([
    new Date(),
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

/** Отправляет готовый файл на почту, если указан адрес. */
function mailResult_(file, result) {
  if (!CONFIG.EMAIL_TO) return;
  var lines = [
    'Файл остатков для загрузки в Ozon Seller готов.',
    '',
    'Строк с остатками: ' + (result.updated || 0),
    'Обнулено: ' + (result.zeroed || 0),
    'Склад: ' + (result.warehouse || '—'),
    '',
    'Ссылка: ' + file.getUrl()
  ];
  if (result.problems && result.problems.length) {
    lines.push('', 'Замечания:', result.problems.join('\n'));
  }
  MailApp.sendEmail({
    to: CONFIG.EMAIL_TO,
    subject: 'Остатки Ozon FBS — ' + file.getName(),
    body: lines.join('\n'),
    attachments: [file.getBlob()]
  });
}
