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
