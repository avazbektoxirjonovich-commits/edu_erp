"""
Bajariladigan jarayonga POSIX resurs chegaralarini qo'yadi (xotira, CPU vaqti).

`resource` moduli faqat Linux/macOS'da mavjud — Windows'da bu modul import
qilinmaydi, shu holda jim o'tib ketamiz (no-op) va himoya faqat subprocess
timeout'ga tayanadi (qarang: sandbox.py).
"""
try:
    import resource

    MEMORY_LIMIT_BYTES = 128 * 1024 * 1024  # 128 MB
    CPU_LIMIT_SECONDS = 10

    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    except (ValueError, OSError):
        pass
except ImportError:
    pass
