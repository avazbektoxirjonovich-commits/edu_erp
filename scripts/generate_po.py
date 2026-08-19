# -*- coding: utf-8 -*-
"""
Generate locale/{uz,ru,en}/LC_MESSAGES/django.po from translations_data.py.

Run this after adding/editing entries in translations_data.py, then run
compile_translations.py to produce the .mo files Django actually reads.

Usage: python scripts/generate_po.py
"""
import datetime
import os

from translations_data import TRANSLATIONS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.join(BASE_DIR, 'locale')

# GNU gettext's context separator. A TRANSLATIONS key of the form
# "<context>\x04<msgid>" disambiguates two identical source strings that
# must translate differently (e.g. Uzbek "S" meaning Tuesday vs Saturday
# in a single-letter calendar strip) via Django's {% translate %} ... context
# "..." tag / pgettext(), without changing what the source language shows.
CTX_SEP = '\x04'

HEADER = '''msgid ""
msgstr ""
"Project-Id-Version: Qorako'l Ilm Ziyo ERP\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: {date}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: {lang}\\n"

'''


def po_escape(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def write_po(lang, translated_field, out_path):
    lines = [HEADER.format(date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M%z'), lang=lang)]
    for key in sorted(TRANSLATIONS.keys()):
        entry = TRANSLATIONS[key]
        if CTX_SEP in key:
            context, msgid = key.split(CTX_SEP, 1)
        else:
            context, msgid = None, key
        msgstr = entry[translated_field] if translated_field else msgid
        if context is not None:
            lines.append(f'msgctxt "{po_escape(context)}"\n')
        lines.append(f'msgid "{po_escape(msgid)}"\n')
        lines.append(f'msgstr "{po_escape(msgstr)}"\n\n')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    targets = [
        ('uz', None),   # identity: source language, msgstr == msgid
        ('ru', 'ru'),
        ('en', 'en'),
    ]
    for lang, field in targets:
        out_dir = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'django.po')
        write_po(lang, field, out_path)
        print(f'{lang}: wrote {len(TRANSLATIONS)} entries -> {out_path}')


if __name__ == '__main__':
    main()
