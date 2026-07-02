"""
Talaba yuborgan kodni xavfsiz bajarish uchun yagona kirish nuqtasi.

Oldingi versiya import/funksiya nomlarini statik blocklist (matn qidirish)
orqali tekshirardi — bu `__imp` + `ort os` kabi oddiy usullar bilan chetlab
o'tilishi mumkin edi. Hozir ikki backend mavjud:

- "restricted" (default): RestrictedPython yordamida kompilyatsiya va runtime
  bosqichida xavfsizlikni ta'minlaydi (qarang: sandbox_runner.py), alohida
  subprocess'da timeout bilan ishga tushiriladi. Docker talab qilmaydi.
- "docker": har bir bajarishni alohida, tarmoqsiz, xotira/CPU chegaralangan
  konteynerda ishga tushiradi. Bu loyiha muhitida Docker daemon mavjud
  bo'lmagani uchun sinovdan o'tkazilmagan — production'da ishlatishdan oldin
  tekshirib chiqing.

Backend tanlovi: settings.CODE_EXECUTION_BACKEND ('restricted' yoki 'docker').
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings

_RUNNER_PATH = Path(__file__).resolve().parent / 'sandbox_runner.py'


def _execute_restricted(code: str, stdin_input: str, timeout: int) -> str:
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, dir=tempfile.gettempdir(), encoding='utf-8'
    ) as f:
        f.write(code)
        f.flush()
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, str(_RUNNER_PATH), tmp_path],
            input=stdin_input, capture_output=True, text=True,
            timeout=timeout, cwd=tempfile.gettempdir(),
        )
        if result.returncode != 0:
            err = result.stderr[:500].replace(tmp_path, '<fayl>')
            return err if err.startswith('XATO:') else f"XATO: {err}"
        return result.stdout
    except subprocess.TimeoutExpired:
        return f"XATO: Vaqt chegarasi oshdi ({timeout} soniya)"
    except Exception as exc:
        return f"XATO: {str(exc)[:200]}"
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass


def _execute_docker(code: str, stdin_input: str, timeout: int) -> str:
    try:
        import docker
    except ImportError:
        return "XATO: 'docker' python paketi o'rnatilmagan — CODE_EXECUTION_BACKEND='restricted' qiling"

    client = docker.from_env()
    with tempfile.TemporaryDirectory() as tmp_dir:
        code_file = Path(tmp_dir) / 'student_code.py'
        code_file.write_text(code, encoding='utf-8')

        try:
            container = client.containers.run(
                image='python:3.11-slim',
                command=['python', '/sandbox/student_code.py'],
                volumes={str(tmp_dir): {'bind': '/sandbox', 'mode': 'ro'}},
                working_dir='/sandbox',
                network_disabled=True,
                mem_limit='128m',
                nano_cpus=1_000_000_000,  # 1 CPU
                read_only=True,
                tmpfs={'/tmp': 'size=16m'},
                stdin_open=True,
                detach=True,
            )
            try:
                exit_status = container.wait(timeout=timeout)
                logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
                if exit_status.get('StatusCode', 1) != 0:
                    return f"XATO: {logs[:500]}"
                return logs
            finally:
                container.remove(force=True)
        except Exception as exc:
            return f"XATO: docker bajarishda muammo: {str(exc)[:300]}"


def execute_student_code(code: str, stdin_input: str = '', timeout: int = 5) -> str:
    """Talaba kodini sozlangan backend orqali bajaradi va stdout/xato matnini qaytaradi."""
    backend = getattr(settings, 'CODE_EXECUTION_BACKEND', 'restricted')
    if backend == 'docker':
        return _execute_docker(code, stdin_input, timeout)
    return _execute_restricted(code, stdin_input, timeout)
