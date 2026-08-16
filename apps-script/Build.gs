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
