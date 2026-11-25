"""Команды бота: /check запускает внеочередную проверку на этом ПК.

Запускается Планировщиком раз в минуту и ~50 с ждёт сообщений (long polling),
поэтому бот отвечает почти сразу. Команды принимаются только из TELEGRAM_CHAT_ID.
"""
import os
import re
import subprocess

import requests

from .main import ROOT, load_env

OFFSET_FILE = ROOT / "logs" / "tg_offset.txt"
FLAG_FILE = ROOT / "logs" / "manual_check.flag"
TASK_NAME = "PS5 Sniper"
CHECK = re.compile(r"^\s*(/check(@\w+)?|проверь|проверка|check)\s*$", re.I)
HELP = "Команды:\n/check — проверить Makler прямо сейчас (ПК должен быть включён)"


def parse_updates(updates: list, chat_id: str):
    """-> (следующий offset или None, нужна ли проверка, было ли другое сообщение от владельца)."""
    offset, check, other = None, False, False
    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != str(chat_id):
            continue  # чужие чаты игнорируем
        if CHECK.match(msg.get("text") or ""):
            check = True
        else:
            other = True
    return offset, check, other


def main():
    load_env(ROOT / ".env")
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    api = f"https://api.telegram.org/bot{token}/"
    OFFSET_FILE.parent.mkdir(exist_ok=True)
    if not OFFSET_FILE.exists():
        requests.post(api + "setMyCommands", json={"commands": [
            {"command": "check", "description": "Проверить Makler сейчас"}]}, timeout=20)
        OFFSET_FILE.write_text("0")
    offset = int(OFFSET_FILE.read_text() or 0)

    r = requests.get(api + "getUpdates", params={"offset": offset, "timeout": 50,
                                                 "allowed_updates": '["message"]'}, timeout=70)
    r.raise_for_status()
    new_offset, check, other = parse_updates(r.json().get("result", []), chat)
    if new_offset is not None:
        OFFSET_FILE.write_text(str(new_offset))

    def say(text):
        requests.post(api + "sendMessage", data={"chat_id": chat, "text": text}, timeout=20)

    if check:
        FLAG_FILE.write_text("1")
        res = subprocess.run(["schtasks", "/Run", "/TN", TASK_NAME], capture_output=True)
        say("🔎 Проверяю Makler, это займёт около минуты…" if res.returncode == 0
            else "⚠️ Не удалось запустить проверку на ПК (задача Планировщика не найдена).")
    elif other:
        say(HELP)


if __name__ == "__main__":
    main()
