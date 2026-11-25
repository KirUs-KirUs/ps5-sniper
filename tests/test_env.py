from sniper.main import load_env


def test_load_env_reads_file_without_overriding(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# comment\nTELEGRAM_BOT_TOKEN = "123:abc"\nTELEGRAM_CHAT_ID=42\n\n', encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "from-env")
    load_env(f)
    import os
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "123:abc"
    assert os.environ["TELEGRAM_CHAT_ID"] == "from-env"


def test_load_env_missing_file_is_ok(tmp_path):
    load_env(tmp_path / "nope.env")
