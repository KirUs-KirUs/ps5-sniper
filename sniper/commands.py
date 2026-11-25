"""Команды бота: /check запускает внеочередную проверку на этом ПК.

Запускается Планировщиком раз в минуту и ~50 с ждёт сообщений (long polling),
поэтому бот отвечает почти сразу. Команды принимаются только из TELEGRAM_CHAT_ID.
"""
import os
import re
import subprocess

import requests

from .main import ROOT, load_env, load_json, new_state, sorted_active
from .notify import format_list

OFFSET_FILE = ROOT / "logs" / "tg_offset.txt"
FLAG_FILE = ROOT / "logs" / "manual_check.flag"
COMMANDS_SET_FILE = ROOT / "logs" / "tg_commands_v2.txt"
TASK_NAME = "PS5 Sniper"
COMMANDS = {
    "check": re.compile(r"^\s*(/check(@\w+)?|проверь|проверка|check)\s*$", re.I),
    "list": re.compile(r"^\s*(/list(@\w+)?|список|list)\s*$", re.I),
}
HELP = ("Команды:\n/check — проверить Makler прямо сейчас (ПК должен быть включён)\n"
        "/list — текущий список подходящих PS5")


def parse_command(text: str):
    for name, rx in COMMANDS.items():
        if rx.match(text or ""):
            return name
    return None


def parse_updates(updates: list, chat_id: str):
    """-> (следующий offset или None, набор команд владельца: check / list / help)."""
    offset, cmds = None, set()
    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != str(chat_id):
            continue  # чужие чаты игнорируем
        cmds.add(parse_command(msg.get("text")) or "help")
    return offset, cmds


def main():
    load_env(ROOT / ".env")
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    api = f"https://api.telegram.org/bot{token}/"
    OFFSET_FILE.parent.mkdir(exist_ok=True)
    if not OFFSET_FILE.exists():
        OFFSET_FILE.write_text("0")
    if not COMMANDS_SET_FILE.exists():
        requests.post(api + "setMyCommands", json={"commands": [
            {"command": "check", "description": "Проверить Makler сейчас"},
            {"command": "list", "description": "Текущий список PS5"}]}, timeout=20)
        COMMANDS_SET_FILE.write_text("2")
    offset = int(OFFSET_FILE.read_text() or 0)

    r = requests.get(api + "getUpdates", params={"offset": offset, "timeout": 50,
                                                 "allowed_updates": '["message"]'}, timeout=70)
    r.raise_for_status()
    new_offset, cmds = parse_updates(r.json().get("result", []), chat)
    if new_offset is not None:
        OFFSET_FILE.write_text(str(new_offset))

    def say(text, html=False):
        data = {"chat_id": chat, "text": text, "disable_web_page_preview": "true"}
        if html:
            data["parse_mode"] = "HTML"
        requests.post(api + "sendMessage", data=data, timeout=20)

    if "list" in cmds:
        cfg = load_json(ROOT / "config.json", None)
        state = load_json(ROOT / "data" / "state.json", new_state())
        now = state["health"].get("last_ok") or state["health"].get("last_run")
        items = sorted_active(cfg, state["listings"], now) if now else []
        say(format_list(items, cfg["deal_usd"], state["health"].get("last_ok")), html=True)
    if "check" in cmds:
        FLAG_FILE.write_text("1")
        res = subprocess.run(["schtasks", "/Run", "/TN", TASK_NAME], capture_output=True)
        say("🔎 Проверяю Makler, это займёт около минуты…" if res.returncode == 0
            else "⚠️ Не удалось запустить проверку на ПК (задача Планировщика не найдена).")
    if cmds == {"help"}:
        say(HELP)


if __name__ == "__main__":
    main()
