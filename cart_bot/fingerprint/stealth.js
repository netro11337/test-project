// Скрипт подмены отпечатка. Выполняется в каждом документе (включая iframe)
// ДО любого скрипта страницы — Playwright гарантирует это через add_init_script.
//
// Плейсхолдер __FINGERPRINT__ подставляется из Python (JSON-объект профиля).
(() => {
  "use strict";

  const FP = __FINGERPRINT__;

  /* ------------------------------------------------------------------ *
   * 1. Инфраструктура: делаем патчи неотличимыми от нативных функций.
   *    Наивное `navigator.webdriver = false` ловится проверкой
   *    Object.getOwnPropertyDescriptor, а подменённая функция выдаёт себя
   *    через toString(). Ниже — общая обвязка, чтобы этого не было.
   * ------------------------------------------------------------------ */

  const nativeToString = Function.prototype.toString;
  const fakeSources = new WeakMap();

  const asNative = (fn, name) => {
    fakeSources.set(fn, `function ${name}() { [native code] }`);
    return fn;
  };

  const toStringProxy = new Proxy(nativeToString, {
    apply(target, thisArg, args) {
      if (fakeSources.has(thisArg)) return fakeSources.get(thisArg);
      return Reflect.apply(target, thisArg, args);
    },
  });
  fakeSources.set(toStringProxy, "function toString() { [native code] }");
  Function.prototype.toString = toStringProxy;

  // Подменяем свойство там, где оно реально объявлено (обычно — на прототипе).
  const overrideGetter = (obj, prop, value) => {
    let target = obj;
    while (target && !Object.getOwnPropertyDescriptor(target, prop)) {
      target = Object.getPrototypeOf(target);
    }
    target = target || obj;
    const descriptor = Object.getOwnPropertyDescriptor(target, prop) || {};
    const getter = asNative(function () {
      return typeof value === "function" ? value.call(this) : value;
    }, `get ${prop}`);
    Object.defineProperty(target, prop, {
      get: getter,
      set: descriptor.set,
      configurable: true,
      enumerable: descriptor.enumerable !== false,
    });
  };

  const overrideMethod = (obj, prop, impl) => {
    const original = obj[prop];
    const wrapper = asNative(function (...args) {
      return impl.call(this, original, ...args);
    }, prop);
    Object.defineProperty(obj, prop, {
      value: wrapper,
      writable: true,
      configurable: true,
      enumerable: Object.getOwnPropertyDescriptor(obj, prop)?.enumerable ?? false,
    });
  };

  // Детерминированный ГПСЧ (xorshift32): один и тот же seed -> один и тот же шум,
  // поэтому отпечаток стабилен внутри профиля, но отличается между профилями.
  const makeRng = (seed) => {
    let s = (seed >>> 0) || 0x9e3779b9;
    return () => {
      s ^= s << 13; s >>>= 0;
      s ^= s >>> 17;
      s ^= s << 5;  s >>>= 0;
      return s / 4294967296;
    };
  };

  /* ------------------------------------------------------------------ *
   * 2. Признаки автоматизации
   * ------------------------------------------------------------------ */

  // navigator.webdriver: в настоящем Chrome геттер есть и возвращает false.
  overrideGetter(Navigator.prototype, "webdriver", false);

  // Следы CDP/Selenium в объекте window и document.
  for (const key of Object.keys(window)) {
    if (/^[$_]?(cdc_|selenium|webdriver|driver-evaluate|fxdriver)/i.test(key)) {
      delete window[key];
    }
  }
  for (const attr of ["webdriver", "selenium", "driver"]) {
    document.documentElement?.removeAttribute?.(attr);
  }

  /* ------------------------------------------------------------------ *
   * 3. navigator: UA, платформа, языки, железо
   * ------------------------------------------------------------------ */

  overrideGetter(Navigator.prototype, "userAgent", FP.user_agent);
  overrideGetter(Navigator.prototype, "appVersion", FP.app_version);
  overrideGetter(Navigator.prototype, "platform", FP.platform);
  overrideGetter(Navigator.prototype, "vendor", "Google Inc.");
  overrideGetter(Navigator.prototype, "language", FP.languages[0]);
  overrideGetter(Navigator.prototype, "languages", Object.freeze([...FP.languages]));
  overrideGetter(Navigator.prototype, "hardwareConcurrency", FP.hardware_concurrency);
  overrideGetter(Navigator.prototype, "deviceMemory", FP.device_memory);
  overrideGetter(Navigator.prototype, "maxTouchPoints", FP.max_touch_points);

  // User-Agent Client Hints: должны совпадать с UA и с sec-ch-* заголовками.
  if (window.NavigatorUAData) {
    const brands = Object.freeze(FP.ua_brands.map((b) => Object.freeze({ ...b })));
    overrideGetter(NavigatorUAData.prototype, "brands", brands);
    overrideGetter(NavigatorUAData.prototype, "mobile", false);
    overrideGetter(NavigatorUAData.prototype, "platform", FP.ua_data_platform);
    overrideMethod(NavigatorUAData.prototype, "getHighEntropyValues", function (_orig, hints) {
      const full = {
        architecture: FP.ua_data_architecture,
        bitness: FP.ua_data_bitness,
        brands: brands.map((b) => ({ ...b })),
        fullVersionList: brands.map((b) => ({
          brand: b.brand,
          version: b.brand === "Not;A=Brand" ? "99.0.0.0" : FP.chrome_full_version,
        })),
        mobile: false,
        model: FP.ua_data_model,
        platform: FP.ua_data_platform,
        platformVersion: FP.ua_data_platform_version,
        uaFullVersion: FP.chrome_full_version,
        wow64: false,
        formFactors: ["Desktop"],
      };
      const result = { brands: full.brands, mobile: false, platform: full.platform };
      for (const hint of hints || []) {
        if (hint in full) result[hint] = full[hint];
      }
      return Promise.resolve(result);
    });
    overrideMethod(NavigatorUAData.prototype, "toJSON", function () {
      return { brands: brands.map((b) => ({ ...b })), mobile: false, platform: FP.ua_data_platform };
    });
  }

  /* ------------------------------------------------------------------ *
   * 4. Экран и окно
   * ------------------------------------------------------------------ */

  overrideGetter(Screen.prototype, "width", FP.screen_width);
  overrideGetter(Screen.prototype, "height", FP.screen_height);
  overrideGetter(Screen.prototype, "availWidth", FP.avail_width);
  overrideGetter(Screen.prototype, "availHeight", FP.avail_height);
  overrideGetter(Screen.prototype, "availLeft", 0);
  overrideGetter(Screen.prototype, "availTop", 0);
  overrideGetter(Screen.prototype, "colorDepth", FP.color_depth);
  overrideGetter(Screen.prototype, "pixelDepth", FP.color_depth);

  overrideGetter(window, "devicePixelRatio", FP.device_scale_factor);
  overrideGetter(window, "outerWidth", () => window.innerWidth);
  overrideGetter(window, "outerHeight", () => window.innerHeight + FP.outer_height_delta);
  overrideGetter(window, "screenX", 0);
  overrideGetter(window, "screenY", 0);
  overrideGetter(window, "screenLeft", 0);
  overrideGetter(window, "screenTop", 0);

  /* ------------------------------------------------------------------ *
   * 5. window.chrome и Permissions API
   * ------------------------------------------------------------------ */

  if (!window.chrome) {
    Object.defineProperty(window, "chrome", { value: {}, writable: true, configurable: true, enumerable: true });
  }
  if (!window.chrome.runtime) window.chrome.runtime = {};
  if (!window.chrome.app) {
    window.chrome.app = {
      isInstalled: false,
      InstallState: { DISABLED: "disabled", INSTALLED: "installed", NOT_INSTALLED: "not_installed" },
      RunningState: { CANNOT_RUN: "cannot_run", READY_TO_RUN: "ready_to_run", RUNNING: "running" },
      getDetails: asNative(function getDetails() { return null; }, "getDetails"),
      getIsInstalled: asNative(function getIsInstalled() { return false; }, "getIsInstalled"),
    };
  }
  if (!window.chrome.csi) {
    window.chrome.csi = asNative(function csi() {
      const t = performance.timing || {};
      return { onloadT: t.domContentLoadedEventEnd || Date.now(), startE: t.navigationStart || Date.now(),
               pageT: performance.now(), tran: 15 };
    }, "csi");
  }
  if (!window.chrome.loadTimes) {
    window.chrome.loadTimes = asNative(function loadTimes() {
      return { requestTime: performance.timeOrigin / 1000, startLoadTime: performance.timeOrigin / 1000,
               commitLoadTime: performance.timeOrigin / 1000, finishLoadTime: performance.timeOrigin / 1000,
               navigationType: "Other", wasNpnNegotiated: true, npnNegotiatedProtocol: "h2",
               wasAlternateProtocolAvailable: false, connectionInfo: "h2" };
    }, "loadTimes");
  }

  // Классический маркер headless: Notification.permission === 'denied',
  // при этом permissions.query отвечает 'prompt'. Приводим к согласию.
  if (window.Notification) {
    overrideGetter(Notification, "permission", "default");
  }
  if (window.Permissions) {
    overrideMethod(Permissions.prototype, "query", function (original, parameters) {
      if (parameters && parameters.name === "notifications") {
        return Promise.resolve({ state: Notification.permission, name: "notifications", onchange: null });
      }
      return Reflect.apply(original, this, [parameters]);
    });
  }

  /* ------------------------------------------------------------------ *
   * 6. Плагины и mimeTypes (у headless-Chrome список пуст — это заметно)
   * ------------------------------------------------------------------ */

  (() => {
    if (!window.PluginArray || !window.Plugin) return;
    const pdfMimes = [
      { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
      { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" },
    ];
    const pluginData = [
      "PDF Viewer", "Chrome PDF Viewer", "Chromium PDF Viewer",
      "Microsoft Edge PDF Viewer", "WebKit built-in PDF",
    ];

    const mimeTypes = [];
    const plugins = pluginData.map((name) => {
      const plugin = Object.create(Plugin.prototype);
      const own = { name, description: "Portable Document Format", filename: "internal-pdf-viewer", length: 2 };
      for (const [key, value] of Object.entries(own)) {
        Object.defineProperty(plugin, key, { get: asNative(() => value, `get ${key}`), enumerable: true, configurable: true });
      }
      pdfMimes.forEach((mime, i) => {
        const mimeType = Object.create(MimeType.prototype);
        for (const [key, value] of Object.entries({ ...mime, enabledPlugin: plugin })) {
          Object.defineProperty(mimeType, key, { get: asNative(() => value, `get ${key}`), enumerable: true, configurable: true });
        }
        Object.defineProperty(plugin, i, { value: mimeType, enumerable: true, configurable: true });
        Object.defineProperty(plugin, mime.type, { value: mimeType, configurable: true });
        mimeTypes.push(mimeType);
      });
      return plugin;
    });

    const makeArray = (proto, items, keyOf) => {
      const array = Object.create(proto);
      items.forEach((item, i) => Object.defineProperty(array, i, { value: item, enumerable: true, configurable: true }));
      items.forEach((item) => Object.defineProperty(array, keyOf(item), { value: item, configurable: true }));
      Object.defineProperty(array, "length", { get: asNative(() => items.length, "get length"), configurable: true });
      overrideMethod(array, "item", function (_o, i) { return items[i] ?? null; });
      overrideMethod(array, "namedItem", function (_o, name) { return items.find((x) => keyOf(x) === name) ?? null; });
      Object.defineProperty(array, Symbol.iterator, { value: function* () { yield* items; }, configurable: true });
      return array;
    };

    const pluginArray = makeArray(PluginArray.prototype, plugins, (p) => p.name);
    const mimeTypeArray = makeArray(MimeTypeArray.prototype, mimeTypes, (m) => m.type);
    overrideGetter(Navigator.prototype, "plugins", pluginArray);
    overrideGetter(Navigator.prototype, "mimeTypes", mimeTypeArray);
    overrideGetter(Navigator.prototype, "pdfViewerEnabled", true);
  })();

  /* ------------------------------------------------------------------ *
   * 7. WebGL: вендор/рендерер (самый весомый компонент отпечатка)
   * ------------------------------------------------------------------ */

  (() => {
    const UNMASKED_VENDOR = 0x9245;   // 37445
    const UNMASKED_RENDERER = 0x9246; // 37446
    const contexts = [window.WebGLRenderingContext, window.WebGL2RenderingContext].filter(Boolean);

    for (const ctx of contexts) {
      overrideMethod(ctx.prototype, "getParameter", function (original, parameter) {
        if (parameter === UNMASKED_VENDOR) return FP.webgl_vendor;
        if (parameter === UNMASKED_RENDERER) return FP.webgl_renderer;
        if (parameter === this.VENDOR) return "WebKit";
        if (parameter === this.RENDERER) return "WebKit WebGL";
        return Reflect.apply(original, this, [parameter]);
      });
      // Некоторые проверки читают вендора через сам объект расширения.
      overrideMethod(ctx.prototype, "getExtension", function (original, name) {
        const ext = Reflect.apply(original, this, [name]);
        if (name === "WEBGL_debug_renderer_info" && !ext) {
          return { UNMASKED_VENDOR_WEBGL: UNMASKED_VENDOR, UNMASKED_RENDERER_WEBGL: UNMASKED_RENDERER };
        }
        return ext;
      });
    }
  })();

  /* ------------------------------------------------------------------ *
   * 8. Canvas: детерминированный шум вместо точного хеша
   *    Полностью «чистая» канва даёт стабильный хеш, по которому вас узнают
   *    на разных сайтах. Добавляем едва заметный сдвиг пикселей.
   * ------------------------------------------------------------------ */

  (() => {
    const noiseAmplitude = Math.max(1, Math.round(FP.canvas_noise * 255));

    const perturb = (imageData, seed) => {
      const rng = makeRng(seed ^ FP.seed);
      const data = imageData.data;
      // Трогаем ~1 канал из 32 — достаточно, чтобы сломать хеш,
      // и мало, чтобы изображение осталось визуально прежним.
      for (let i = 0; i < data.length; i += 4) {
        if (rng() > 0.03) continue;
        const channel = i + ((rng() * 3) | 0);
        const delta = rng() > 0.5 ? noiseAmplitude : -noiseAmplitude;
        data[channel] = Math.min(255, Math.max(0, data[channel] + delta));
      }
      return imageData;
    };

    if (window.CanvasRenderingContext2D) {
      overrideMethod(CanvasRenderingContext2D.prototype, "getImageData", function (original, ...args) {
        const imageData = Reflect.apply(original, this, args);
        return perturb(imageData, (args[2] | 0) * 31 + (args[3] | 0));
      });
    }

    // toDataURL / toBlob читают пиксели в обход getImageData, поэтому
    // рисуем во временную канву и зашумляем её, не трогая видимую.
    const noisyClone = (canvas) => {
      try {
        const clone = document.createElement("canvas");
        clone.width = canvas.width;
        clone.height = canvas.height;
        const ctx = clone.getContext("2d");
        ctx.drawImage(canvas, 0, 0);
        // getImageData здесь уже пропатчен выше, значит клон получает шум.
        ctx.putImageData(ctx.getImageData(0, 0, clone.width, clone.height), 0, 0);
        return clone;
      } catch {
        return canvas;
      }
    };

    if (window.HTMLCanvasElement) {
      overrideMethod(HTMLCanvasElement.prototype, "toDataURL", function (original, ...args) {
        if (!this.width || !this.height) return Reflect.apply(original, this, args);
        return Reflect.apply(original, noisyClone(this), args);
      });
      overrideMethod(HTMLCanvasElement.prototype, "toBlob", function (original, ...args) {
        if (!this.width || !this.height) return Reflect.apply(original, this, args);
        return Reflect.apply(original, noisyClone(this), args);
      });
    }
  })();

  /* ------------------------------------------------------------------ *
   * 9. AudioContext: тот же приём — микрошум в аудио-отпечатке
   * ------------------------------------------------------------------ */

  (() => {
    const amp = FP.audio_noise;
    if (window.AudioBuffer) {
      overrideMethod(AudioBuffer.prototype, "getChannelData", function (original, channel) {
        const data = Reflect.apply(original, this, [channel]);
        const rng = makeRng(FP.seed + channel);
        for (let i = 0; i < data.length; i += 100) {
          data[i] += (rng() - 0.5) * amp;
        }
        return data;
      });
    }
    if (window.AnalyserNode) {
      for (const method of ["getFloatFrequencyData", "getByteFrequencyData"]) {
        overrideMethod(AnalyserNode.prototype, method, function (original, array) {
          Reflect.apply(original, this, [array]);
          const rng = makeRng(FP.seed ^ array.length);
          for (let i = 0; i < array.length; i += 50) {
            array[i] += (rng() - 0.5) * (method === "getFloatFrequencyData" ? amp * 1e3 : 0);
          }
          return undefined;
        });
      }
    }
  })();

  /* ------------------------------------------------------------------ *
   * 10. Таймзона: Playwright задаёт её на уровне браузера, но JS-объект
   *     Intl мы всё равно проверяем, чтобы resolvedOptions не расходился.
   * ------------------------------------------------------------------ */

  (() => {
    const wanted = FP.timezone;
    const actual = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (actual === wanted) return; // уже выставлено на уровне контекста
    overrideMethod(Intl.DateTimeFormat.prototype, "resolvedOptions", function (original) {
      return { ...Reflect.apply(original, this, []), timeZone: wanted, locale: FP.locale };
    });
  })();
})();
