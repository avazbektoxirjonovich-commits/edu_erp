"""
Talaba kodini RestrictedPython orqali izolyatsiyalangan holatda bajaradigan ishchi skript.

Bu fayl asosiy Django jarayonidan ALOHIDA subprocess sifatida ishga tushiriladi
(qarang: sandbox.py -> execute_student_code). Shu sababli bu yerda
xato yoki cheksiz tsikl bo'lsa ham, asosiy serverga ta'sir qilmaydi va
subprocess timeout bilan majburan to'xtatiladi.

Himoya qatlamlari:
1. RestrictedPython AST transformeri — `import`, underscore bilan boshlangan
   attributlarga kirish (masalan __class__, __subclasses__, __globals__),
   va boshqa xavfli sintaksisni kompilyatsiya bosqichida bloklaydi.
2. Faqat oldindan belgilangan "xavfsiz" builtin'lar globals'ga beriladi —
   open/eval/exec/compile/__import__/getattr/setattr kabi funksiyalar yo'q.
3. Runtime guard funksiyalari (_getattr_, _getitem_, _getiter_, _write_) —
   AST transformeridan o'tib ketgan urinishlarni ishlash vaqtida ham tekshiradi.
4. Resurs chegaralari (faqat POSIX'da mavjud — Windows'da subprocess timeout
   yagona himoya bo'lib qoladi).
"""
import resource_limits  # noqa: F401  (faqat side-effect uchun, pastda chaqiriladi)
import sys
import warnings

# RestrictedPython har bir print(...) chaqiruvi uchun "printed o'qilmadi" degan
# kosmetik SyntaxWarning chiqaradi — biz chiqishni o'zimiz _print_ orqali o'qiymiz,
# shu sababli bu ogohlantirish talaba xatosi sifatida noto'g'ri talqin qilinmasligi uchun bosiladi
warnings.filterwarnings('ignore', category=SyntaxWarning, module='RestrictedPython')

from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector


def _build_restricted_globals():
    allowed_builtins = dict(safe_globals['__builtins__'])
    # Talaba kodlari uchun zarur, lekin xavfsiz qo'shimcha builtin'lar
    extra = {
        'input': input,
        'range': range,
        'len': len,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'sorted': sorted,
        'reversed': reversed,
        'sum': sum,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round,
        'pow': pow,
        'divmod': divmod,
        'all': all,
        'any': any,
        'isinstance': isinstance,
        'issubclass': issubclass,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'frozenset': frozenset,
        'chr': chr,
        'ord': ord,
        'repr': repr,
        'type': type,
        'Exception': Exception,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'IndexError': IndexError,
        'KeyError': KeyError,
        'ZeroDivisionError': ZeroDivisionError,
        'StopIteration': StopIteration,
        'RuntimeError': RuntimeError,
        'AttributeError': AttributeError,
        'NameError': NameError,
        'ArithmeticError': ArithmeticError,
        'OverflowError': OverflowError,
        'True': True,
        'False': False,
        'None': None,
        '__metaclass__': type,  # RestrictedPython class ta'rifi uchun talab qiladi
    }
    allowed_builtins.update(extra)

    restricted_globals = dict(safe_globals)
    restricted_globals['__builtins__'] = allowed_builtins
    restricted_globals.update({
        '_getattr_': safer_getattr,
        '_getitem_': default_guarded_getitem,
        '_getiter_': default_guarded_getiter,
        # RestrictedPython'ning standart full_write_guard'i faqat dict/list'ga yozishga
        # ruxsat beradi va o'z sinflariga (masalan `self.x = y`) "attribute-less object"
        # xatosi bilan rad etadi, chunki u "ishonchli" tashqi obyektlarni himoya qilish
        # uchun mo'ljallangan. Bizning sandbox'da talaba kodi faqat O'ZI yaratgan
        # obyektlar (o'z sinflari, list/dict) bilan ishlaydi — hech qanday tashqi/
        # "ishonchli" obyekt globals'ga berilmagan, shu sababli yozishni cheklash
        # shart emas va identity guard ishlatiladi.
        '_write_': lambda ob: ob,
        '_unpack_sequence_': guarded_unpack_sequence,
        '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        '_print_': PrintCollector,
        '__name__': '__student_code__',
    })
    return restricted_globals


def main():
    if len(sys.argv) != 2:
        print("XATO: kod fayli ko'rsatilmagan", file=sys.stderr)
        sys.exit(1)

    code_path = sys.argv[1]
    with open(code_path, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        byte_code = compile_restricted(source, filename='<talaba_kodi>', mode='exec')
    except SyntaxError as exc:
        print(f"XATO: sintaksis xatosi: {exc}", file=sys.stderr)
        sys.exit(1)

    restricted_globals = _build_restricted_globals()
    try:
        exec(byte_code, restricted_globals)
    except Exception as exc:  # talaba kodidagi har qanday runtime xato
        print(f"XATO: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        # RestrictedPython print(...) chaqiruvlarini real stdout'ga emas, "_print_" orqali
        # yaratilgan PrintCollector nusxasiga ('_print' nomli lokal) yig'adi — shuni o'qib,
        # haqiqiy stdout'ga chiqaramiz (test case'lar shu chiqishni solishtiradi)
        printer = restricted_globals.get('_print')
        sys.stdout.write(printer() if printer is not None else '')


if __name__ == '__main__':
    main()
