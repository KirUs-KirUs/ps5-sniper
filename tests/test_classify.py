import pytest

from sniper.classify import classify

# (title, text, is_ps5, model, disc)
CASES = [
    ("PS5 SLIM 1 TB с дисководом + 2 геимпада+GTA 6", "", True, "Slim", "yes"),
    ("Продам PS 5 Slim", "Состояние отличное", True, "Slim", "unknown"),
    ("Sony PlayStation 5", "", True, "PS5", "unknown"),
    ("Sony Playstation 5 Digital Edition", "", False, None, "no"),
    ("PS5 Digital + дисковод", "", True, "PS5", "yes"),
    ("Плейстейшн 5 про", "", True, "Pro", "unknown"),
    ("ПС5 фат с приводом", "", True, "Fat", "yes"),
    ("PS5 Pro без дисковода", "", False, None, "no"),
    ("PlayStation 5 Pro 2TB + дисковод в комплекте", "", True, "Pro", "yes"),
    ("Playstation 5 + 3 игры и геймпад", "Blu-ray работает", True, "PS5", "yes"),
    ("Продам приставку", "PS5 slim, дисковод, 2 джойстика", True, "Slim", "yes"),
    ("ps5", "", True, "PS5", "unknown"),
    ("PlayStation5 Slim Disc Edition", "", True, "Slim", "yes"),
    # исключения
    ("Подписка PS PLUS и игры на PlayStation", "PS5", False, None, None),
    ("Gamepad PS5. ps4 Магазин Гарантия", "PS5 Slim от 650уе", False, None, None),
    ("Аренда посуточно PlayStation 5 + GTA6", "", False, None, None),
    ("Обмен iPhone 15 Pro Max на PS5 (Fat / Slim / Pro)", "", False, None, None),
    ("Скупаю по выгодной цене", "PS5, PS4", False, None, None),
    ("Куплю PS5", "", False, None, None),
    ("Диски для PS5", "", False, None, None),
    ("Игры PS5,PS4 и подписки PS Plus Extra", "", False, None, None),
    ("Продам Silent hill 2 для PS5 Games| PlayStation 5", "", False, None, None),
    ("Дисковод для PS5 Pro", "", False, None, None),
    ("Геймпад DualSense PS5", "", False, None, None),
    ("PlayStation 4 Pro 1 TB", "", False, None, None),
    ("Xbox Series S 512GB в коробке", "можно обменять на ps5", False, None, None),
    ("Ремонт PS5, PS4", "", False, None, None),
    ("PS5 на запчасти", "", False, None, None),
    ("SONY PLAYSTATION Portal", "для PS5", False, None, None),
    ("Продам турецкий аккаунт PS Store", "PS5", False, None, None),
    ("Death stranding на пс4,5", "", False, None, None),
]


@pytest.mark.parametrize("title,text,is_ps5,model,disc", CASES)
def test_classify(title, text, is_ps5, model, disc):
    r = classify(title, text)
    assert r["is_ps5"] is is_ps5, r
    if is_ps5:
        assert r["model"] == model
        assert r["disc"] == disc
    elif disc is not None:
        assert r["disc"] == disc
