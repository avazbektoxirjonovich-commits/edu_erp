"""
Compile locale/*/LC_MESSAGES/django.po -> django.mo without requiring the
GNU gettext toolchain (msgfmt) to be installed on the machine.

Why this exists: Django's `manage.py compilemessages` shells out to the
real `msgfmt` binary. This dev machine only has gettext-runtime (the
`gettext` lookup tool), not gettext-tools (msgfmt/msgmerge/xgettext), and
installing the full toolchain on Windows requires an external package
manager. This script implements the GNU MO binary format directly
(a well-documented, simple format) so translations work without it.

On a Linux deployment (Render, CI, etc.) where gettext-tools is normally
preinstalled, prefer the standard `python manage.py compilemessages`
instead — this script is a portability fallback for this environment.

Usage: python scripts/compile_translations.py
"""
import array
import os
import struct
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_DIR = os.path.join(BASE_DIR, 'locale')


def _dequote(line):
    """Strip one pair of surrounding double quotes from a PO string token."""
    line = line.strip()
    if line.startswith('"') and line.endswith('"') and len(line) >= 2:
        return line[1:-1]
    return line


def _unescape(text):
    """Decode PO backslash escapes (\\n \\t \\" \\\\) into real characters."""
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            out.append({'n': '\n', 't': '\t', '"': '"', '\\': '\\'}.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def parse_po(path):
    """Minimal .po parser supporting multi-line msgid/msgstr continuations
    and msgctxt (GNU gettext context disambiguation)."""
    entries = {}

    def finalize(ctxt_parts, msgid_parts, msgstr_parts, fuzzy):
        if msgid_parts is None:
            return
        msgid = _unescape(''.join(msgid_parts))
        msgstr = _unescape(''.join(msgstr_parts))
        if ctxt_parts:
            # GNU gettext convention: context + \x04 + msgid is the real lookup
            # key, matching what Python's gettext.pgettext() (and Django's
            # {% translate %} ... context "..." tag) look up at runtime.
            msgid = _unescape(''.join(ctxt_parts)) + '\x04' + msgid
        # Keep the header entry (empty msgid) — gettext reads charset from its
        # msgstr metadata block. Only real translations need a non-empty msgstr.
        if fuzzy:
            return
        if msgid == '' or msgstr:
            entries[msgid] = msgstr

    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    ctxt_parts, msgid_parts, msgstr_parts = None, None, None
    mode = None  # 'ctxt' | 'id' | 'str' | None
    fuzzy = False

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith('#,') and 'fuzzy' in stripped:
            fuzzy = True
            continue
        if stripped.startswith('#'):
            continue
        if stripped.startswith('msgctxt '):
            finalize(ctxt_parts, msgid_parts, msgstr_parts, fuzzy)
            ctxt_parts = [_dequote(stripped[len('msgctxt '):])]
            msgid_parts, msgstr_parts = None, None
            mode = 'ctxt'
            fuzzy = False
            continue
        if stripped.startswith('msgid '):
            if mode != 'ctxt':
                finalize(ctxt_parts, msgid_parts, msgstr_parts, fuzzy)
                ctxt_parts = None
                fuzzy = False
            msgid_parts = [_dequote(stripped[len('msgid '):])]
            msgstr_parts = []
            mode = 'id'
            continue
        if stripped.startswith('msgstr '):
            msgstr_parts = [_dequote(stripped[len('msgstr '):])]
            mode = 'str'
            continue
        if stripped.startswith('"'):
            if mode == 'ctxt':
                ctxt_parts.append(_dequote(stripped))
            elif mode == 'id':
                msgid_parts.append(_dequote(stripped))
            elif mode == 'str':
                msgstr_parts.append(_dequote(stripped))
            continue
        # any other directive — not used in this project, ignore
    finalize(ctxt_parts, msgid_parts, msgstr_parts, fuzzy)
    return entries


def write_mo(entries, out_path):
    """Write a GNU MO file (little-endian, no hash table)."""
    keys = sorted(entries.keys())
    ids = b''
    strs = b''
    offsets = []
    for k in keys:
        v = entries[k]
        k_b = k.encode('utf-8')
        v_b = v.encode('utf-8')
        offsets.append((len(ids), len(k_b), len(strs), len(v_b)))
        ids += k_b + b'\x00'
        strs += v_b + b'\x00'

    n = len(keys)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    koffsets, voffsets = [], []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]

    header = struct.pack(
        '<Iiiiiii',
        0x950412de,              # magic
        0,                        # version
        n,                        # number of strings
        7 * 4,                    # offset of table with original strings
        7 * 4 + n * 8,             # offset of table with translation strings
        0, 0,                      # size and offset of hash table (unused)
    )
    body = array.array('i', koffsets + voffsets)
    body.byteswap() if sys.byteorder == 'big' else None

    with open(out_path, 'wb') as f:
        f.write(header)
        f.write(body.tobytes())
        f.write(ids)
        f.write(strs)


def main():
    if not os.path.isdir(LOCALE_DIR):
        print(f'No locale dir at {LOCALE_DIR}')
        sys.exit(1)
    total = 0
    for lang in sorted(os.listdir(LOCALE_DIR)):
        po_path = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.po')
        mo_path = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', 'django.mo')
        if not os.path.isfile(po_path):
            continue
        entries = parse_po(po_path)
        write_mo(entries, mo_path)
        print(f'{lang}: {len(entries)} translations -> {mo_path}')
        total += len(entries)
    print(f'Done. {total} total translation entries compiled.')


if __name__ == '__main__':
    main()
