/**
 * Логика. СОБИРАЕТСЯ АВТОМАТИЧЕСКИ — при обновлении заменяйте этот файл
 * целиком, настройки лежат отдельно, в файле «Настройки».
 *
 * Правьте исходники в apps-script/ и запускайте tools/build-single-file.sh.
 */

// ===================================================================
// Utils.gs
// ===================================================================

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

  var dates = [];
  for (var b = 0; b < blocks.length; b++) {
    if (blocks[b].date) dates.push(blocks[b].date);
  }
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
    dateLabel: chosen.dateLabel,
    dates: dates
  };
}

/** Ключ даты через N дней от сегодня (0 — сегодня, 1 — завтра). */
function dayShiftKey_(days) {
  var n = new Date();
  var d = new Date(n.getFullYear(), n.getMonth(), n.getDate() + days);
  return dateKey_(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

/**
 * Что будет взято на указанную дату — словами. Нужно, чтобы заранее увидеть,
 * отработает ли автозапуск завтра, не дожидаясь утра.
 */
function describePick_(dates, key) {
  if (!dates.length) return 'дат на листе нет — берётся весь лист';

  var prev = null;
  for (var i = 0; i < dates.length; i++) {
    if (dates[i] === key) return 'будет взят блок ' + dateLabel_(key);
    if (dates[i] < key && (prev === null || dates[i] > prev)) prev = dates[i];
  }
  if (CONFIG.DATE_FALLBACK === 'previous' && prev !== null) {
    return 'блока нет, возьмётся предыдущий — ' + dateLabel_(prev);
  }
  return 'блока нет, файл НЕ будет создан';
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
  var year = new Date().getFullYear();
  var marks = [];
  var r, c, i;

  // Размечаем лист: где строки заголовков, а где строки с датой
  for (r = 0; r < values.length; r++) {
    var s = matchColumn_(values[r], skuAliases);
    var q = matchColumn_(values[r], qtyAliases);
    if (s !== -1 && q !== -1) {
      marks.push({ type: 'header', row: r, skuCol: s, qtyCol: q });
      continue;
    }
    var d = null;
    for (c = 0; c < values[r].length; c++) {
      d = parseSheetDate_(values[r][c], year);
      if (d) break;
    }
    if (d) marks.push({ type: 'date', row: r, date: d });
  }

  var blocks = [];
  var cols = null;                // последние встреченные заголовки
  var pendingDate = null, pendingDateRow = null;

  for (i = 0; i < marks.length; i++) {
    var m = marks[i];

    if (m.type === 'header') {
      cols = m;
      blocks.push({
        headerRow: m.row,
        skuCol: m.skuCol,
        qtyCol: m.qtyCol,
        date: pendingDate,
        dateRow: pendingDateRow,
        dataStart: m.row + 1
      });
      pendingDate = null;
      pendingDateRow = null;
      continue;
    }

    // Строка с датой. Если сразу под ней свои заголовки — блок откроют они.
    var next = marks[i + 1];
    if (next && next.type === 'header' && next.row - m.row <= 2) {
      pendingDate = m.date;
      pendingDateRow = m.row;
      continue;
    }

    // Заголовков нет — берём колонки предыдущего блока: на листе принято
    // писать «sku / остатки» один раз, а дальше только даты.
    if (cols) {
      blocks.push({
        headerRow: cols.row,
        skuCol: cols.skuCol,
        qtyCol: cols.qtyCol,
        date: m.date,
        dateRow: m.row,
        dataStart: m.row + 1
      });
    }
  }

  for (i = 0; i < blocks.length; i++) {
    var stop = values.length;
    if (i + 1 < blocks.length) {
      var nb = blocks[i + 1];
      stop = nb.dateRow !== null ? nb.dateRow : nb.headerRow;
    }
    blocks[i].dataEnd = stop - 1;
  }
  return blocks;
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

// ===================================================================
// Fill.gs
// ===================================================================

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
  var source = readSourceStocks_(shop);
  var templateFolder = folderById_(shop.templateFolderId,
    'шаблон' + (shop.name ? ' магазина ' + shop.name : ' из ЛК'));
  // Заголовок «Шаблон из ЛК» в отчёте одинаков для Ozon и WB — площадку
  // видно по имени файла и по названию магазина.
  var outFolder = folderById_(shop.outputFolderId, 'готовые файлы');

  var templateFile = latestTemplateFile_(templateFolder, shop.templateFile);
  var tmpId = convertToSheet_(templateFile, 'tmp-ozon-' + stamp_());

  try {
    var result = applyStocks_(tmpId, source, shop);
    result.dateLabel = source.dateLabel;
    var fileName = outputFileName_(shop);
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

/**
 * Показывает, какой шаблон привязан к каждому магазину и какие склады
 * в нём лежат. Файлов не создаёт — нужен, чтобы один раз убедиться,
 * что папки не перепутаны: сам по шаблону скрипт этого понять не может.
 */
function checkTemplates() {
  var shops = shopsList_();
  var lines = [];

  for (var i = 0; i < shops.length; i++) {
    var shop = shops[i];
    lines.push('— ' + (shop.name || 'магазин') +
      ' (' + (shop.platform === 'wb' ? 'Wildberries' : 'Ozon') + ') —');

    var tmpId = null;
    try {
      var folder = folderById_(shop.templateFolderId, 'шаблон ' + shop.name);
      var file = latestTemplateFile_(folder, shop.templateFile);
      lines.push('Папка: ' + folder.getName());
      lines.push('Файл: ' + file.getName());

      tmpId = convertToSheet_(file, 'tmp-check-' + stamp_());
      var ss = SpreadsheetApp.openById(tmpId);
      var sheets = ss.getSheets();
      var loc = null;
      for (var k = 0; k < sheets.length; k++) {
        loc = locateColumns_(sheets[k], shop);
        if (loc) break;
      }

      if (!loc) {
        lines.push('НЕ РАЗОБРАН: не найдены колонки кода товара и количества.');
      } else {
        lines.push('Колонки распознаны, данные пишутся со строки ' +
          findDataStart_(loc.sheet, loc) + '.');
        if (loc.warehouseCol === -1) {
          lines.push('Склад в файле не указывается.');
        } else {
          var opts = warehouseOptions_(loc.sheet, loc, findDataStart_(loc.sheet, loc));
          lines.push(opts.length
            ? 'Склады в шаблоне: ' + opts.join(' | ')
            : 'Список складов в шаблоне не найден.');
        }
      }
    } catch (e) {
      lines.push('ОШИБКА: ' + e.message);
    } finally {
      if (tmpId) trashQuietly_(tmpId);
    }
    lines.push('');
  }

  lines.push('Сверьте склады с кабинетами: если у магазина показан чужой склад,',
    'значит в его папку попал шаблон другого кабинета.');
  tell_('Проверка шаблонов', lines.join('\n'));
}

/** Имя готового файла: площадка, магазин, дата. */
function outputFileName_(shop) {
  return 'ostatki-' + (shop && shop.platform === 'wb' ? 'wb' : 'ozon') + '-' +
    (shop && shop.name ? slug_(shop.name) + '-' : '') + stamp_() + '.xlsx';
}

/**
 * Шаблон магазина в папке. Если задан templateFile, берётся файл, в имени
 * которого он встречается, — так несколько шаблонов могут лежать в одной
 * папке. Иначе берётся самый свежий файл.
 */
function latestTemplateFile_(folder, pattern) {
  var pat = normHeader_(pattern || '');
  var files = folder.getFiles();
  var best = null;
  var seen = [];

  while (files.hasNext()) {
    var f = files.next();
    var name = f.getName();
    var low = normHeader_(name);
    if (low.indexOf('.xls') === -1) continue;
    if (low.indexOf('ostatki-') === 0) continue;         // это наш же результат
    seen.push(name);
    if (pat && low.indexOf(pat) === -1) continue;
    if (!best || f.getLastUpdated() > best.getLastUpdated()) best = f;
  }

  if (best) return best;

  if (pat) {
    throw new Error('В папке «' + folder.getName() + '» нет файла .xls/.xlsx ' +
      'со словом «' + pattern + '» в названии. Что лежит в папке: ' +
      (seen.length ? seen.join(', ') : 'ничего подходящего') + '.');
  }
  throw new Error('В папке «' + folder.getName() +
    '» нет ни одного файла .xls/.xlsx. Положите туда шаблон, скачанный из ЛК.');
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
    loc = locateColumns_(sheets[s], shop);
    if (loc) break;
  }
  if (!loc) {
    throw new Error('В шаблоне не найден лист с колонками «' +
      (shop && shop.platform === 'wb' ? 'баркод' : 'артикул') +
      '» и количества. Откройте шаблон, посмотрите точные названия колонок ' +
      'и добавьте их в HEADER_ALIASES в файле Config.gs.');
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
    row[loc.skuCol] = String(item.raw);
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

  // Баркод 13 знаков и артикул с ведущими нулями должны остаться текстом,
  // иначе Google превратит их в число и потеряет нули или точность.
  sheet.getRange(dataStart, loc.skuCol + 1, existing.length, 1)
    .setNumberFormat('@');
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
function locateColumns_(sheet, shop) {
  var lastRow = Math.min(sheet.getLastRow(), 20);
  var lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return null;

  var idAliases = idAliasesFor_(shop);
  var head = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  for (var r = 0; r < head.length; r++) {
    var skuCol = matchColumn_(head[r], idAliases);
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

  var wanted = (shop && shop.warehouse) ||
    (shop && shop.platform === 'wb' ? '' : CONFIG.WAREHOUSE_NAME) || '';
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
  if (shop && shop.platform === 'wb') return '';   // у WB склад выбирается в ЛК
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
    if (r.dateLabel) lines.push('Остатки за: ' + r.dateLabel);
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

// ===================================================================
// Build.gs
// ===================================================================

/**
 * Режим Б — запасной.
 *
 * Собирает файл остатков с нуля, повторяя структуру шаблона FBS:
 * склад | артикул | название товара | доступно на складе, шт.
 *
 * Режим А (Fill.gs) надёжнее: там формат гарантированно совпадает
 * с тем, что ждёт личный кабинет, а название склада подставляется
 * из выпадающего списка самого шаблона.
 */
function buildStockFile() {
  var shops = shopsList_();
  var results = [];
  var errors = [];

  for (var i = 0; i < shops.length; i++) {
    try {
      var r = buildOneShop_(shops[i]);
      results.push(r);
      logRun_(r);
    } catch (e) {
      var where = shops[i].name ? shops[i].name + ': ' : '';
      errors.push(where + e.message);
      logRun_({ shop: shops[i].name, mode: 'Ошибка', problems: [e.message] });
    }
  }

  mailResults_(results, errors);
  tell_(results.length ? 'Готово' : 'Не получилось', report_(results, errors));

  if (!results.length) {
    throw new Error(errors.join('\n'));
  }
  return results;
}

/** Собирает файл с нуля для одного магазина. */
function buildOneShop_(shop) {
  var source = readSourceStocks_(shop);
  var outFolder = folderById_(shop.outputFolderId, 'готовые файлы');
  var warehouse = shop.warehouse || CONFIG.WAREHOUSE_NAME;

  if (!warehouse) {
    if (shop.platform !== 'wb') {
      throw new Error('Для сборки файла с нуля нужно название склада ровно ' +
        'как в личном кабинете — укажите его в настройках.');
    }
  }

  var tmp = SpreadsheetApp.create('tmp-ozon-build-' + stamp_());
  var tmpId = tmp.getId();

  try {
    var sheet = tmp.getSheets()[0];
    sheet.setName('Остатки');

    var rows = [[
      CONFIG.OUT_WAREHOUSE_HEADER,
      CONFIG.OUT_SKU_HEADER,
      CONFIG.OUT_NAME_HEADER,
      CONFIG.OUT_QTY_HEADER
    ]];
    for (var i = 0; i < source.rows.length; i++) {
      rows.push([
        warehouse,
        source.rows[i].raw,
        source.rows[i].name || '',
        source.rows[i].qty
      ]);
    }

    sheet.getRange(1, 1, rows.length, 4).setValues(rows);
    // Артикулы вида 00123 не должны потерять ведущие нули
    sheet.getRange(2, 2, source.rows.length, 1).setNumberFormat('@');
    SpreadsheetApp.flush();

    var fileName = outputFileName_(shop);
    var out = exportXlsx_(tmpId, fileName, outFolder);

    return {
      shop: shop.name,
      mode: 'Файл с нуля',
      updated: source.rows.length,
      added: source.rows.length,
      zeroed: 0,
      warehouse: warehouse,
      dateLabel: source.dateLabel,
      problems: source.problems,
      fileName: fileName,
      fileUrl: out.getUrl(),
      file: out
    };
  } finally {
    trashQuietly_(tmpId);
  }
}

// ===================================================================
// Menu.gs
// ===================================================================

/**
 * Меню в таблице, проверка данных и ежедневный автозапуск.
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Остатки')
    .addItem('Проверить данные', 'checkSource')
    .addItem('Проверить шаблоны', 'checkTemplates')
    .addSeparator()
    .addItem('Заполнить шаблон(ы) из ЛК', 'fillOzonTemplate')
    .addItem('Собрать файл(ы) с нуля', 'buildStockFile')
    .addSeparator()
    .addItem('Включить ежедневный запуск', 'setupDailyTrigger')
    .addItem('Выключить ежедневный запуск', 'removeDailyTrigger')
    .addToUi();
}

/** Быстрая проверка листов с остатками — без создания файлов. */
function checkSource() {
  var shops = shopsList_();
  var lines = [];

  for (var s = 0; s < shops.length; s++) {
    if (shops[s].name) lines.push('— ' + shops[s].name + ' (лист «' + shops[s].sheet + '») —');

    try {
      var source = readSourceStocks_(shops[s]);
      var total = 0, zeros = 0;
      for (var i = 0; i < source.rows.length; i++) {
        total += source.rows[i].qty;
        if (source.rows[i].qty === 0) zeros++;
      }
      if (source.dateLabel) lines.push('Остатки за: ' + source.dateLabel);
      lines.push('Строк с товарами: ' + source.rows.length);
      lines.push('Из них с нулевым остатком: ' + zeros);
      lines.push('Суммарное количество: ' + total);
      if (source.problems.length) {
        lines.push('Замечания (' + source.problems.length + '):',
          source.problems.slice(0, 15).join('\n'));
      } else {
        lines.push('Ошибок в данных не найдено.');
      }
      if (source.dates.length) {
        var labels = [];
        for (var d = 0; d < source.dates.length; d++) {
          labels.push(dateLabel_(source.dates[d]));
        }
        lines.push('Даты на листе: ' + labels.join(', '));
        var t = dayShiftKey_(1);
        lines.push('Завтра (' + dateLabel_(t) + '): ' + describePick_(source.dates, t));
      }
    } catch (e) {
      lines.push('ОШИБКА: ' + e.message);
    }
    lines.push('');
  }
  tell_('Проверка данных', lines.join('\n'));
}

/** Функция, которую дёргает ежедневный триггер. */
function dailyRun() {
  try {
    if (CONFIG.DAILY_MODE === 'build') {
      buildStockFile();
    } else {
      fillOzonTemplate();
    }
  } catch (e) {
    logRun_({
      mode: 'Автозапуск — ошибка',
      problems: [e.message]
    });
    if (CONFIG.EMAIL_TO) {
      MailApp.sendEmail(CONFIG.EMAIL_TO,
        'Остатки: автозапуск не сработал',
        'Ошибка: ' + e.message +
        '\n\nОткройте таблицу и запустите «Остатки → Заполнить шаблон(ы) из ЛК» вручную.');
    }
    throw e;
  }
}

function setupDailyTrigger() {
  removeDailyTrigger();
  ScriptApp.newTrigger('dailyRun')
    .timeBased()
    .atHour(CONFIG.DAILY_HOUR)
    .nearMinute(0)
    .everyDays(1)
    .create();
  tell_('Автозапуск включён',
    'Файл будет готовиться каждый день около ' + CONFIG.DAILY_HOUR + ':00.' +
    (CONFIG.EMAIL_TO ? '\nГотовый файл придёт на ' + CONFIG.EMAIL_TO + '.'
                     : '\nГотовый файл будет появляться в папке на Google Диске.'));
}

function removeDailyTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'dailyRun') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
}

