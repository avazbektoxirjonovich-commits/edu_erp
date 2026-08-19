# -*- coding: utf-8 -*-
"""
Extract every literal string used in {% translate %} / {% blocktranslate %}
across all templates, and report which ones are missing from
translations_data.py. Read-only diagnostic tool.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translations_data import TRANSLATIONS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
CTX_SEP = '\x04'  # matches generate_po.py / compile_translations.py convention

# {% translate "..." [context "..."] [as var] %}, double-quoted message
RE_DQ = re.compile(r'\{%\s*translate\s+"((?:[^"\\]|\\.)*)"(?:\s+context\s+"((?:[^"\\]|\\.)*)")?')
# same, single-quoted message
RE_SQ = re.compile(r"\{%\s*translate\s+'((?:[^'\\]|\\.)*)'(?:\s+context\s+'((?:[^'\\]|\\.)*)')?")
# {% blocktranslate ... %}...{% endblocktranslate %} (possibly with asvar)
RE_BLOCK = re.compile(r'\{%\s*blocktranslate[^%]*%\}(.*?)\{%\s*endblocktranslate\s*%\}', re.DOTALL)


def _key(msgid, context):
    return f'{context}{CTX_SEP}{msgid}' if context else msgid


def find_all_msgids():
    found = {}  # msgid (or context\x04msgid) -> list of files
    for path in glob.glob(os.path.join(TEMPLATES_DIR, '**', '*.html'), recursive=True):
        rel = os.path.relpath(path, BASE_DIR)
        with open(path, encoding='utf-8') as f:
            content = f.read()
        for m in RE_DQ.finditer(content):
            found.setdefault(_key(m.group(1), m.group(2)), []).append(rel)
        for m in RE_SQ.finditer(content):
            found.setdefault(_key(m.group(1), m.group(2)), []).append(rel)
        for m in RE_BLOCK.finditer(content):
            s = m.group(1).strip()
            found.setdefault(s, []).append(rel)
    return found


def main():
    found = find_all_msgids()
    missing = sorted(k for k in found if k not in TRANSLATIONS)
    extra = sorted(k for k in TRANSLATIONS if k not in found)

    print(f'Total unique msgids found in templates: {len(found)}')
    print(f'Already translated: {len(found) - len(missing)}')
    print(f'MISSING from translations_data.py: {len(missing)}')
    print()
    out_path = os.path.join(BASE_DIR, 'scripts', '_missing_msgids.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        for m in missing:
            f.write(m.replace('\n', '\\n') + '\n')
    print(f'Wrote missing list to {out_path}')

    if extra:
        print(f'\n{len(extra)} entries in translations_data.py not currently used in any template (harmless, but listed):')
        for e in extra[:30]:
            print('  -', e.replace(chr(10), '\\n'))
        if len(extra) > 30:
            print(f'  ...and {len(extra)-30} more')


if __name__ == '__main__':
    main()
