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

// ===================================================================
// Config.gs
// ===================================================================

/**
 * Настройки скрипта. В обычной работе правится только этот файл.
 *
 * Сценарий: FBS, обновление остатков через загрузку файла в личный кабинет
 * Ozon Seller (без Seller API).
 */
var CONFIG = {
  // ---------------------------------------------------------------------
  // Лист вашей таблицы, где лежат данные «sku -> сколько должно быть»
  // ---------------------------------------------------------------------
  SOURCE_SHEET: 'Остатки',

  // Заголовки колонок на этом листе. Регистр и лишние пробелы не важны.
  SKU_HEADER: 'sku',
  QTY_HEADER: 'остаток',

  // ---------------------------------------------------------------------
  // Режим А (основной): заполняем шаблон, скачанный из личного кабинета
  // ---------------------------------------------------------------------
  // ID папки на Google Диске, куда вы кладёте скачанный из ЛК шаблон.
  // ID — это кусок из адреса папки: drive.google.com/drive/folders/<ID>
  TEMPLATE_FOLDER_ID: '',

  // ID папки, куда складывать готовые файлы для загрузки в ЛК.
  // Можно указать ту же папку, что и TEMPLATE_FOLDER_ID.
  OUTPUT_FOLDER_ID: '',

  // Необязательная колонка с названием товара на вашем листе.
  // Пусто — колонка «Название товара» в файле останется пустой,
  // Ozon её не требует.
  NAME_HEADER: '',

  // ---------------------------------------------------------------------
  // Склад
  // ---------------------------------------------------------------------
  // Название склада ровно как в выпадающем списке шаблона Ozon.
  // Можно оставить пустым: если в шаблоне склад один, скрипт подставит его
  // сам, а если складов несколько — покажет список и попросит выбрать.
  WAREHOUSE_NAME: '',

  // Что делать с товарами, которые уже перечислены в шаблоне, но
  // отсутствуют в вашей таблице:
  //   'keep' — оставить количество как есть
  //   'zero' — проставить 0
  // Для пустого шаблона из ЛК не играет роли: в нём нет готовых строк.
  MISSING_SKU_ACTION: 'keep',

  // ---------------------------------------------------------------------
  // Режим Б (запасной): собираем файл с нуля, без шаблона из ЛК
  // ---------------------------------------------------------------------
  // Заголовки колонок в файле, который собирается с нуля.
  // Так они называются в шаблоне остатков FBS.
  OUT_WAREHOUSE_HEADER: 'Название склада (идентификатор склада)',
  OUT_SKU_HEADER: 'Артикул',
  OUT_NAME_HEADER: 'Название товара',
  OUT_QTY_HEADER: 'Доступно на складе, шт',

  // ---------------------------------------------------------------------
  // Автозапуск
  // ---------------------------------------------------------------------
  // Куда присылать готовый файл. Пусто — письмо не отправляется,
  // файл просто появляется в папке OUTPUT_FOLDER_ID.
  EMAIL_TO: '',

  // Час ежедневного запуска (0-23), часовой пояс — из appsscript.json.
  DAILY_HOUR: 8,

  // Какой режим запускать по расписанию: 'template' (А) или 'build' (Б).
  DAILY_MODE: 'template'
};

/**
 * Варианты названий колонок, которые скрипт умеет распознавать
 * автоматически — и в вашей таблице, и в шаблоне Ozon.
 * Если в шаблоне окажется незнакомое название — просто допишите его сюда.
 */
var HEADER_ALIASES = {
  sku: [
    'артикул',
    'артикул товара',
    'артикул продавца',
    'ваш артикул',
    'offer_id',
    'sku',
    'ваш sku'
  ],
  qty: [
    'доступно на складе, шт',
    'доступно на складе',
    'количество',
    'кол-во',
    'остаток',
    'остатки',
    'доступное количество',
    'количество товара'
  ],
  warehouse: [
    'название склада (идентификатор склада)',
    'название склада',
    'идентификатор склада',
    'имя склада',
    'склад'
  ],
  name: [
    'название товара',
    'наименование товара',
    'название'
  ]
};

/**
 * Строки под заголовком, которые Ozon использует под подсказки
 * («Редактируемое обязательное», «Укажите артикул товара…»).
 * Скрипт распознаёт их по этим началам строк и не трогает.
 */
var SERVICE_ROW_MARKERS = [
  'редактируем',
  'не редактируем',
  'обязательное',
  'необязательное',
  'укажите',
  'выберите',
  'заполните'
];

/** Лист, в который пишется история запусков. Создаётся автоматически. */
var LOG_SHEET = 'Лог';

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
 * Находит в конвертированном шаблоне лист с товарами и заполняет его.
 * Строки, которые уже есть в шаблоне, обновляются на месте; всё остальное
 * из таблицы дописывается ниже.
 * @return {Object} статистика для отчёта.
 */
function applyStocks_(spreadsheetId, source) {
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
  var warehouse = resolveWarehouse_(sheet, loc, dataStart);
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
    notInTemplate: 0,
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
function resolveWarehouse_(sheet, loc, dataStart) {
  if (loc.warehouseCol === -1) return '';

  var options = warehouseOptions_(sheet, loc, dataStart);

  if (CONFIG.WAREHOUSE_NAME) {
    if (options.length && options.indexOf(CONFIG.WAREHOUSE_NAME) === -1) {
      throw new Error('Склад «' + CONFIG.WAREHOUSE_NAME +
        '» не найден в шаблоне. Доступные варианты: ' + options.join(' | ') +
        '. Скопируйте название точь-в-точь в CONFIG.WAREHOUSE_NAME.');
    }
    return CONFIG.WAREHOUSE_NAME;
  }

  if (options.length === 1) return options[0];
  if (options.length > 1) {
    throw new Error('В шаблоне несколько складов: ' + options.join(' | ') +
      '. Впишите нужный в CONFIG.WAREHOUSE_NAME.');
  }
  throw new Error('Не удалось определить склад: в шаблоне нет выпадающего списка. ' +
    'Впишите название склада в CONFIG.WAREHOUSE_NAME ровно как в личном кабинете.');
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
function report_(result) {
  var lines = [
    'Файл: ' + result.fileName,
    '',
    'Строк с остатками в файле: ' + result.updated
  ];
  if (result.added) lines.push('Из них дописано в пустой шаблон: ' + result.added);
  if (result.zeroed) lines.push('Обнулено (нет в таблице): ' + result.zeroed);
  if (result.untouched) lines.push('Оставлено без изменений: ' + result.untouched);
  if (result.warehouse) lines.push('Склад: ' + result.warehouse);
  if (result.problems && result.problems.length) {
    lines.push('', 'Замечания:', result.problems.slice(0, 10).join('\n'));
  }
  lines.push('', 'Файл лежит в папке готовых файлов на Google Диске.',
    'Загрузите его в ЛК: Управление логистикой → склад →',
    'Управление остатками → загрузить файл → «Обновить остатки».');
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
  var source = readSourceStocks_();
  var outFolder = folderById_(CONFIG.OUTPUT_FOLDER_ID, 'готовые файлы');

  if (!CONFIG.WAREHOUSE_NAME) {
    throw new Error('Для сборки файла с нуля нужно указать CONFIG.WAREHOUSE_NAME — ' +
      'название склада ровно как в личном кабинете Ozon.');
  }

  var tmp = SpreadsheetApp.create('tmp-ozon-build-' + stamp_());
  var tmpId = tmp.getId();
  var result;

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
        CONFIG.WAREHOUSE_NAME,
        source.rows[i].raw,
        source.rows[i].name || '',
        source.rows[i].qty
      ]);
    }

    sheet.getRange(1, 1, rows.length, 4).setValues(rows);
    // Артикулы вида 00123 не должны потерять ведущие нули
    sheet.getRange(2, 2, source.rows.length, 1).setNumberFormat('@');
    SpreadsheetApp.flush();

    var fileName = 'ozon-ostatki-' + stamp_() + '.xlsx';
    var out = exportXlsx_(tmpId, fileName, outFolder);

    result = {
      mode: 'Файл с нуля',
      updated: source.rows.length,
      added: source.rows.length,
      zeroed: 0,
      warehouse: CONFIG.WAREHOUSE_NAME,
      problems: source.problems,
      fileName: fileName,
      fileUrl: out.getUrl()
    };
    logRun_(result);
    mailResult_(out, result);
  } finally {
    trashQuietly_(tmpId);
  }

  tell_('Файл готов', report_(result));
  return result;
}

// ===================================================================
// Menu.gs
// ===================================================================

/**
 * Меню в таблице, проверка данных и ежедневный автозапуск.
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Ozon')
    .addItem('Проверить данные', 'checkSource')
    .addSeparator()
    .addItem('Заполнить шаблон из ЛК', 'fillOzonTemplate')
    .addItem('Собрать файл с нуля', 'buildStockFile')
    .addSeparator()
    .addItem('Включить ежедневный запуск', 'setupDailyTrigger')
    .addItem('Выключить ежедневный запуск', 'removeDailyTrigger')
    .addToUi();
}

/** Быстрая проверка листа с остатками — без создания файлов. */
function checkSource() {
  var source = readSourceStocks_();
  var total = 0, zeros = 0;
  for (var i = 0; i < source.rows.length; i++) {
    total += source.rows[i].qty;
    if (source.rows[i].qty === 0) zeros++;
  }

  var lines = [
    'Строк с товарами: ' + source.rows.length,
    'Из них с нулевым остатком: ' + zeros,
    'Суммарное количество: ' + total
  ];
  if (source.problems.length) {
    lines.push('', 'Замечания (' + source.problems.length + '):',
      source.problems.slice(0, 15).join('\n'));
  } else {
    lines.push('', 'Ошибок в данных не найдено.');
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
        'Остатки Ozon: автозапуск не сработал',
        'Ошибка: ' + e.message +
        '\n\nОткройте таблицу и запустите «Ozon → Заполнить шаблон из ЛК» вручную.');
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

