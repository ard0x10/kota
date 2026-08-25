"""Translation, keyed on the English string itself.

There is no catalogue to keep in step and no numbering to get wrong: an
untranslated string comes out in English, which is a worse interface but never
a broken one. `set_language` is called at startup and whenever the setting
changes.
"""

import locale

_LANGUAGE = "en"

TURKISH = {
    # The window
    "Session": "Oturum",
    "Week": "Hafta",
    "Extra": "Ek kullanım",
    "resets %s": "%s sonra",
    # The two units a countdown is spelled in: 2 gun 3 saat, 2 saat 48 dakika.
    "d": "g",
    "h": "s",
    "m": "dk",
    "resets now": "şimdi sıfırlanıyor",
    "signed in": "girişli",
    "Add the account signed in now": "Şu an girişli olan hesabı ekle",
    "No accounts yet": "Henüz hesap yok",
    "Sign in to Claude Code, then add the account here. Do it again for the "
    "second one.": "Claude Code'a giriş yap, sonra hesabı buradan ekle. "
                   "İkincisi için aynısını tekrarla.",
    "Refresh": "Yenile",
    "Settings": "Ayarlar",
    "Reading...": "Okunuyor...",
    "updated %s": "%s güncellendi",
    "just now": "az önce",
    "%dm ago": "%d dk önce",
    "%dh ago": "%d sa önce",
    "%dd ago": "%d gün önce",
    "Remove": "Kaldır",
    "Remove %s?": "%s kaldırılsın mı?",
    "kota will forget this account. Nothing is signed out.":
        "kota bu hesabı unutacak. Hiçbir yerden çıkış yapılmaz.",
    "Cancel": "Vazgeç",
    "No account is signed in to Claude Code.":
        "Claude Code'a girişli bir hesap yok.",

    # Settings
    "Start kota when I sign in": "Bilgisayarı açtığımda kota da açılsın",
    "Check every": "Kontrol aralığı",
    "%d minutes": "%d dakika",
    "1 hour": "1 saat",
    "Warn me when a window passes": "Şu eşiği geçince uyar",
    "Appearance": "Görünüm",
    "System": "Sistem",
    "Light": "Açık",
    "Dark": "Koyu",
    "Language": "Dil",
    "Show the percentage on the tray icon":
        "Yüzdeyi tepsi simgesinin üstünde göster",
    "Closing the window keeps kota in the tray":
        "Pencereyi kapatınca kota tepside kalsın",
    "Done": "Tamam",
    "Where things are": "Dosyalar nerede",
    "Tokens are not encrypted on this machine":
        "Bu makinede token'lar şifrelenmiyor",

    # The tray
    "Open kota": "kota'yı aç",
    "Quit": "Çık",
    "Quota is running out": "Kota bitiyor",
    "%s has used %.0f%% of the week": "%s haftalığın %%%.0f'ini kullandı",
    "%s has used %.0f%% of the session": "%s oturumun %%%.0f'ini kullandı",
}

_CATALOGUES = {"tr": TURKISH}


def system_language():
    """The two-letter language this desktop is set to, or "en"."""
    try:
        code = locale.getlocale()[0] or ""
    except ValueError:
        code = ""
    code = code.replace("-", "_").split("_")[0].lower()
    # Windows answers with the language's own name rather than its code.
    if code.startswith("turkish") or code == "tr":
        return "tr"
    return code[:2] if code[:2] in _CATALOGUES else "en"


def set_language(code):
    global _LANGUAGE
    _LANGUAGE = code if code in _CATALOGUES else "en"


def language():
    return _LANGUAGE


def t(text):
    """`text` in the language in use, or the English it already is."""
    return _CATALOGUES.get(_LANGUAGE, {}).get(text, text)
