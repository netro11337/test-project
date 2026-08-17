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
  var sh = findSheet_(name);

  var values = sh.getDataRange().getValues();
  var skuAliases = sourceIdAliases_(shop);
  var qtyAliases = aliasesFor_(CONFIG.QTY_HEADER, HEADER_ALIASES.qty);

  var blocks = findBlocks_(values, skuAliases, qtyAliases);
  if (!blocks.length) {
    throw new Error('На листе «' + name + '» не найдены колонка с кодом товара (' +
      ((shop && shop.platform === 'wb') ? 'баркод' : 'артикул') +
      ') и колонка «' + CONFIG.QTY_HEADER + '».');
  }

  var chosen = pickBlock_(blocks, name);
  var block = chosen.block;
  var headerRow = block.headerRow;
  var skuCol = block.skuCol;
  var qtyCol = block.qtyCol;

  // Название товара — необязательно, Ozon его не требует
  var nameCol = matchColumn_(values[headerRow],
    aliasesFor_(CONFIG.NAME_HEADER, HEADER_ALIASES.name));

  var map = {};
  var rows = [];
  var problems = chosen.notes.slice();

  for (var i = block.dataStart; i <= block.dataEnd; i++) {
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
    throw new Error('На листе «' + name + '» нет ни одной строки с данными' +
      (chosen.dateLabel ? ' на ' + chosen.dateLabel : '') + '.');
  }
  return {
    map: map,
    rows: rows,
    problems: problems,
    dateLabel: chosen.dateLabel
  };
}

/**
 * Разбирает лист на блоки «дата → таблица остатков».
 *
 * Ожидаемый вид (блоки идут один под другим):
 *
 *          17.08
 *   sku    остатки
 *   ART-1     12
 *
 *          18.08
 *   sku    остатки
 *   ART-1     10
 *
 * Дата ищется в одной-двух строках над заголовком. Лист без дат — тоже
 * нормально: получится один блок, как раньше.
 */
function findBlocks_(values, skuAliases, qtyAliases) {
  var heads = [];
  var r, i;

  for (r = 0; r < values.length; r++) {
    var s = matchColumn_(values[r], skuAliases);
    var q = matchColumn_(values[r], qtyAliases);
    if (s === -1 || q === -1) continue;
    heads.push({ headerRow: r, skuCol: s, qtyCol: q, date: null, dateRow: null });
  }

  var year = new Date().getFullYear();

  for (i = 0; i < heads.length; i++) {
    // Выше искать можно только до предыдущего блока, иначе за дату можно
    // принять что-нибудь из его данных
    var floor = i > 0 ? heads[i - 1].headerRow + 1 : 0;

    for (var up = 1; up <= 2; up++) {
      var rowIdx = heads[i].headerRow - up;
      if (rowIdx < floor) break;

      var found = null;
      for (var c = 0; c < values[rowIdx].length; c++) {
        found = parseSheetDate_(values[rowIdx][c], year);
        if (found) break;
      }
      if (found) {
        heads[i].date = found;
        heads[i].dateRow = rowIdx;
        break;
      }
    }
  }

  for (i = 0; i < heads.length; i++) {
    heads[i].dataStart = heads[i].headerRow + 1;
    var stop = values.length;
    if (i + 1 < heads.length) {
      stop = heads[i + 1].dateRow !== null
        ? heads[i + 1].dateRow
        : heads[i + 1].headerRow;
    }
    heads[i].dataEnd = stop - 1;
  }
  return heads;
}

/** Выбирает блок на сегодня. */
function pickBlock_(blocks, sheetName) {
  var dated = [];
  var i;
  for (i = 0; i < blocks.length; i++) {
    if (blocks[i].date) dated.push(blocks[i]);
  }
  if (!dated.length) {
    return { block: blocks[0], notes: [], dateLabel: '' };
  }

  var now = new Date();
  var today = dateKey_(now.getFullYear(), now.getMonth() + 1, now.getDate());
  var exact = null, prev = null;

  for (i = 0; i < dated.length; i++) {
    if (dated[i].date === today) exact = dated[i];
    if (dated[i].date < today && (!prev || dated[i].date > prev.date)) prev = dated[i];
  }

  if (exact) {
    return { block: exact, notes: [], dateLabel: dateLabel_(exact.date) };
  }

  if (CONFIG.DATE_FALLBACK === 'previous' && prev) {
    return {
      block: prev,
      notes: ['На сегодня (' + dateLabel_(today) + ') на листе «' + sheetName +
        '» блока нет, взяты остатки за ' + dateLabel_(prev.date) + '.'],
      dateLabel: dateLabel_(prev.date)
    };
  }

  var all = [];
  for (i = 0; i < dated.length; i++) all.push(dateLabel_(dated[i].date));
  throw new Error('На листе «' + sheetName + '» нет остатков на сегодня (' +
    dateLabel_(today) + '). Даты на листе: ' + all.join(', ') + '.');
}

/** Дата как число 20260817 — так их удобно сравнивать. */
function dateKey_(y, m, d) {
  return y * 10000 + m * 100 + d;
}

function dateLabel_(key) {
  var d = key % 100;
  var m = Math.floor(key / 100) % 100;
  var y = Math.floor(key / 10000);
  return (d < 10 ? '0' + d : d) + '.' + (m < 10 ? '0' + m : m) + '.' + y;
}

/**
 * Дата из ячейки: либо настоящая дата, либо текст «17.08», «17.08.26»,
 * «17/08/2026». Год можно не писать — возьмётся текущий.
 * Обычные числа датами не считаются: это почти всегда количество.
 */
function parseSheetDate_(v, defaultYear) {
  if (v instanceof Date) {
    return dateKey_(v.getFullYear(), v.getMonth() + 1, v.getDate());
  }
  var m = String(v === null || v === undefined ? '' : v).trim()
    .match(/^(\d{1,2})[.\-\/](\d{1,2})(?:[.\-\/](\d{2,4}))?$/);
  if (!m) return null;

  var d = parseInt(m[1], 10);
  var mo = parseInt(m[2], 10);
  var y = m[3] ? parseInt(m[3], 10) : defaultYear;
  if (y < 100) y += 2000;
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  return dateKey_(y, mo, d);
}

/**
 * Ищет лист по названию. Точное совпадение, затем без учёта регистра и
 * лишних пробелов — «НАПАЛМ ОСТАТКИ» и «Напалм остатки» это один лист.
 */
function findSheet_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name);
  if (sh) return sh;

  var wanted = normHeader_(name);
  var sheets = ss.getSheets();
  var names = [];

  for (var i = 0; i < sheets.length; i++) {
    var actual = sheets[i].getName();
    names.push(actual);
    if (normHeader_(actual) === wanted) return sheets[i];
  }

  throw new Error('Не найден лист «' + name + '». Листы в таблице: ' +
    names.join(', ') + '. Поправьте название в настройках (поле sheet).');
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

/** Пишет строку в лист «Лог», если он включён в настройках. */
function logRun_(result) {
  if (!CONFIG.WRITE_LOG) return;

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
    lines.push('  строк: ' + (r.updated || 0) + ', склад: ' + (r.warehouse || '—') +
      (r.dateLabel ? ', остатки за ' + r.dateLabel : ''));
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
      idHeader: raw[i].idHeader || '',
      templateFile: raw[i].templateFile || ''
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
      idHeader: '',
      templateFile: ''
    });
  }
  return list;
}

/**
 * У каждого кабинета свой шаблон со своим списком складов, и перепутать их
 * — значит молча отправить остатки на чужой склад. Поэтому магазины должны
 * различаться либо папкой, либо именем файла внутри общей папки.
 */
function assertDistinctTemplates_(shops) {
  if (shops.length < 2) return;

  var byFolder = {};
  var names = {};
  var i;

  for (i = 0; i < shops.length; i++) {
    if (!shops[i].templateFolderId) {
      throw new Error('У магазина «' + shops[i].name +
        '» не указана папка с шаблоном (templateFolderId).');
    }

    // По name называются готовые файлы: одинаковые имена — одинаковые файлы
    var nameKey = normHeader_(shops[i].name);
    if (names[nameKey]) {
      throw new Error('Два магазина названы одинаково («' + shops[i].name +
        '»). Имена должны различаться — по ним называются готовые файлы.');
    }
    names[nameKey] = true;

    var id = shops[i].templateFolderId;
    if (!byFolder[id]) byFolder[id] = [];
    byFolder[id].push(shops[i]);
  }

  for (var folder in byFolder) {
    if (!Object.prototype.hasOwnProperty.call(byFolder, folder)) continue;
    var group = byFolder[folder];
    if (group.length < 2) continue;

    var patterns = {};
    for (i = 0; i < group.length; i++) {
      var pat = normHeader_(group[i].templateFile);
      if (!pat) {
        throw new Error('Магазины ' + group.map(function (s) { return '«' + s.name + '»'; }).join(', ') +
          ' смотрят в одну папку с шаблонами. Тогда у каждого нужно указать ' +
          'templateFile — часть имени его файла, иначе непонятно, чей шаблон брать.');
      }
      if (patterns[pat]) {
        throw new Error('У магазинов «' + patterns[pat] + '» и «' + group[i].name +
          '» одинаковый templateFile («' + group[i].templateFile +
          '»). Имена файлов должны различаться.');
      }
      patterns[pat] = group[i].name;
    }
  }
}
