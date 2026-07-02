"""
Talaba yuborgan kodni xavfsiz bajarish — Python va C++ qo'llab-quvvatlaydi.

Backendlar:
- Python: RestrictedPython + subprocess (docker opsional)
- C++: g++ kompilyatsiya → bajarish (temp dir ichida)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings

_RUNNER_PATH = Path(__file__).resolve().parent / 'sandbox_runner.py'


# ── Python (restricted) ───────────────────────────────────────────────────

def _execute_python_restricted(code: str, stdin_input: str, timeout: int) -> str:
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, dir=tempfile.gettempdir(), encoding='utf-8'
    ) as f:
        f.write(code)
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


def _execute_python_docker(code: str, stdin_input: str, timeout: int) -> str:
    try:
        import docker
    except ImportError:
        return "XATO: 'docker' paketi yo'q — CODE_EXECUTION_BACKEND='restricted' qiling"

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
                nano_cpus=1_000_000_000,
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


# ── C++ ──────────────────────────────────────────────────────────────────

def _execute_cpp(code: str, stdin_input: str, timeout: int) -> str:
    """g++ bilan compile qilib, bajaradi. Linux/Render uchun g++ o'rnatilgan bo'lishi kerak."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        src  = Path(tmp_dir) / 'sol.cpp'
        exe  = Path(tmp_dir) / 'sol'
        src.write_text(code, encoding='utf-8')

        # Kompilyatsiya
        try:
            compile_res = subprocess.run(
                ['g++', '-std=c++17', '-O2', '-Wall', '-o', str(exe), str(src)],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            return "XATO: g++ topilmadi — server da C++ kompilyatori o'rnatilmagan"
        except subprocess.TimeoutExpired:
            return "XATO: Kompilyatsiya vaqti oshdi (30 s)"

        if compile_res.returncode != 0:
            err = compile_res.stderr[:600].replace(str(src), 'sol.cpp')
            return f"XATO (kompilyatsiya):\n{err}"

        # Bajarish
        try:
            run_res = subprocess.run(
                [str(exe)],
                input=stdin_input, capture_output=True, text=True,
                timeout=timeout,
            )
            if run_res.returncode != 0:
                stderr = run_res.stderr[:300]
                return f"XATO (runtime): {stderr}" if stderr else f"XATO: exit code {run_res.returncode}"
            return run_res.stdout
        except subprocess.TimeoutExpired:
            return f"XATO: Vaqt chegarasi oshdi ({timeout} soniya)"
        except Exception as exc:
            return f"XATO: {str(exc)[:200]}"


# ── Umumiy kirish nuqtasi ────────────────────────────────────────────────

def execute_student_code(
    code: str,
    stdin_input: str = '',
    timeout: int = 5,
    language: str = 'python',
) -> str:
    """
    Talaba kodini bajaradi va stdout / xato matnini qaytaradi.
    language: 'python' | 'cpp' | 'c++'
    """
    lang = language.lower().replace(' ', '')
    if lang in ('cpp', 'c++', 'cplusplus', 'c_plus_plus'):
        return _execute_cpp(code, stdin_input, timeout)

    # Python
    backend = getattr(settings, 'CODE_EXECUTION_BACKEND', 'restricted')
    if backend == 'docker':
        return _execute_python_docker(code, stdin_input, timeout)
    return _execute_python_restricted(code, stdin_input, timeout)
