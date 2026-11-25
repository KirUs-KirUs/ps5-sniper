// PS5 Sniper — виджет Scriptable для iPhone.
// Вставьте ссылку на ваш widget.json в DATA_URL (или в «Parameter» виджета).
// Поддерживаются размеры: Small, Medium, Large.

const DATA_URL = "https://raw.githubusercontent.com/<GITHUB_USER>/<REPO>/main/data/widget.json";

const C = {
  bg1: new Color("#05070f"),
  bg2: new Color("#0a1a3f"),
  blue: new Color("#0070d1"),
  text: new Color("#f2f5ff"),
  dim: new Color("#8a94b3"),
  card: new Color("#ffffff", 0.06),
  deal: new Color("#ffb020"),
  ok: new Color("#2fd27a"),
  warn: new Color("#ffcc00"),
  bad: new Color("#ff4d5e"),
  tri: new Color("#3ddc97"), // △
  cir: new Color("#ff5a6e"), // ○
  crs: new Color("#5aa9ff"), // ✕
  sqr: new Color("#e88df5"), // □
};

const url = (args.widgetParameter || "").trim() || DATA_URL;
const fm = FileManager.local();
const cachePath = fm.joinPath(fm.cacheDirectory(), "ps5_sniper_widget.json");

async function loadData() {
  try {
    const req = new Request(url + "?t=" + Date.now());
    req.timeoutInterval = 15;
    const data = await req.loadJSON();
    if (!data || !data.updated) throw new Error("bad json");
    fm.writeString(cachePath, JSON.stringify(data));
    return { data, offline: false };
  } catch (e) {
    if (fm.fileExists(cachePath)) return { data: JSON.parse(fm.readString(cachePath)), offline: true };
    return { data: null, offline: true };
  }
}

function ago(iso) {
  if (!iso) return "никогда";
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "только что";
  if (min < 60) return `${min} мин назад`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} ч назад`;
  return `${Math.floor(h / 24)} дн назад`;
}

function health(data, offline) {
  if (!data) return { color: C.bad, label: "нет данных" };
  const staleH = (Date.now() - new Date(data.last_ok || 0).getTime()) / 3600000;
  if (data.status === "down") return { color: C.bad, label: "сайт недоступен" };
  if (staleH > 3) return { color: C.warn, label: "давно не обновлялось" };
  if (data.status === "degraded") return { color: C.warn, label: "сбой, повтор" };
  if (offline) return { color: C.warn, label: "офлайн-кэш" };
  return { color: C.ok, label: "работает" };
}

function txt(stack, s, size, color, weight = "regular", lines = 1) {
  const t = stack.addText(String(s));
  t.font = weight === "bold" ? Font.boldSystemFont(size)
    : weight === "semibold" ? Font.semiboldSystemFont(size)
    : weight === "mono" ? Font.boldMonospacedSystemFont(size)
    : Font.systemFont(size);
  t.textColor = color;
  t.lineLimit = lines;
  return t;
}

function psGlyphs(stack, size) {
  const s = stack.addStack();
  s.spacing = 3;
  [["△", C.tri], ["○", C.cir], ["✕", C.crs], ["□", C.sqr]].forEach(([g, c]) => txt(s, g, size, c, "bold"));
}

function header(w, data, hl, compact) {
  const h = w.addStack();
  h.centerAlignContent();
  txt(h, compact ? "PS5" : "PS5 SNIPER", compact ? 13 : 14, C.text, "bold");
  h.addSpacer(6);
  psGlyphs(h, compact ? 9 : 10);
  h.addSpacer();
  const dot = txt(h, "●", 10, hl.color);
  if (!compact) {
    h.addSpacer(4);
    txt(h, hl.label, 10, C.dim);
  }
}

function priceLine(stack, item, size) {
  const color = item.deal ? C.deal : C.text;
  txt(stack, (item.deal ? "🔥 " : "") + item.price, size, color, "bold");
}

function row(w, item) {
  const r = w.addStack();
  r.backgroundColor = C.card;
  r.cornerRadius = 10;
  r.setPadding(6, 8, 6, 8);
  r.centerAlignContent();
  if (item.url) r.url = item.url;
  const left = r.addStack();
  left.layoutVertically();
  const top = left.addStack();
  txt(top, (item.new ? "NEW · " : "") + item.model, 11, item.new ? C.crs : C.dim, "semibold");
  top.addSpacer(4);
  txt(top, (item.disc === "yes" ? "💿" : "❓") + " " + (item.city || ""), 11, C.dim);
  txt(left, item.title, 12, C.text, "regular", 1);
  r.addSpacer();
  priceLine(r, item, 13);
}

function footer(w, data) {
  const f = w.addStack();
  txt(f, `проверка ${ago(data.last_ok)}`, 9, C.dim);
  f.addSpacer();
  txt(f, `всего ${data.count} · 🔥 ${data.deals} · новых ${data.new_24h}`, 9, C.dim);
}

async function build() {
  const { data, offline } = await loadData();
  const fam = config.widgetFamily || "large";
  const w = new ListWidget();
  const g = new LinearGradient();
  g.colors = [C.bg1, C.bg2];
  g.locations = [0, 1];
  g.startPoint = new Point(0, 0);
  g.endPoint = new Point(1, 1);
  w.backgroundGradient = g;
  w.refreshAfterDate = new Date(Date.now() + 30 * 60 * 1000);
  const hl = health(data, offline);

  if (!data) {
    w.setPadding(14, 14, 14, 14);
    header(w, data, hl, fam === "small");
    w.addSpacer();
    txt(w, "Нет данных. Проверьте DATA_URL.", 12, C.dim, "regular", 3);
    return w;
  }
  w.url = data.list_url;

  if (fam === "small") {
    w.setPadding(12, 12, 12, 12);
    header(w, data, hl, true);
    w.addSpacer(6);
    txt(w, "МИН. ЦЕНА", 9, C.dim, "semibold");
    if (data.min) {
      w.url = data.min.url;
      const p = txt(w, data.min.price, 22, data.min.deal ? C.deal : C.text, "bold");
      p.minimumScaleFactor = 0.5;
      txt(w, `${data.min.model} · ${data.min.city}`, 11, C.text, "semibold");
    } else {
      txt(w, "—", 22, C.text, "bold");
    }
    w.addSpacer();
    txt(w, `🆕 ${data.new_24h} за сутки · 🔥 ${data.deals}`, 10, C.crs, "semibold");
    txt(w, ago(data.last_ok), 9, C.dim);
    return w;
  }

  w.setPadding(12, 12, 10, 12);
  header(w, data, hl, false);
  w.addSpacer(6);

  if (data.min) {
    const s = w.addStack();
    s.centerAlignContent();
    txt(s, "от ", 11, C.dim);
    txt(s, data.min.price, 18, data.min.deal ? C.deal : C.text, "bold");
    s.addSpacer(6);
    txt(s, `${data.min.model} · ${data.min.city}`, 11, C.dim);
    s.url = data.min.url;
    w.addSpacer(6);
  }

  const n = fam === "medium" ? 2 : 6;
  const items = (data.top || []).slice(0, n);
  if (!items.length) txt(w, "Подходящих объявлений пока нет", 12, C.dim);
  items.forEach((it, i) => {
    row(w, it);
    if (i < items.length - 1) w.addSpacer(4);
  });
  w.addSpacer();
  footer(w, data);
  return w;
}

const widget = await build();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentLarge();
}
Script.complete();
