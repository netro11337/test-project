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
      problems: source.problems,
      fileName: fileName,
      fileUrl: out.getUrl(),
      file: out
    };
  } finally {
    trashQuietly_(tmpId);
  }
}
