"""
pytest root conftest — loads Django settings via pytest.ini.
"""
import django
from django.conf import settings


def pytest_configure(config):
    """Ensure ANTHROPIC_API_KEY is set to a dummy for tests so LLMClient init
    does not raise during import. Tests that touch LLM must mock it."""
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy-key-not-real")
