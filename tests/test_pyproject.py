"""tests/test_pyproject.py — Verify pyproject.toml build-system correctness.

These tests guard against regressions where the build-backend is set to the
legacy setuptools shim (setuptools.backends.legacy:build) that causes
``pip install -e ".[dev]"`` to fail with exit code 2.

Reference:
  https://setuptools.pypa.io/en/latest/build_meta.html
"""
from __future__ import annotations

from pathlib import Path

import pytest

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _read_pyproject() -> str:
    return _PYPROJECT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Build-system correctness
# ---------------------------------------------------------------------------


class TestBuildBackend:
    def test_correct_build_backend_present(self):
        """pyproject.toml must declare setuptools.build_meta as build-backend."""
        content = _read_pyproject()
        assert 'build-backend = "setuptools.build_meta"' in content, (
            "pyproject.toml must set build-backend to 'setuptools.build_meta'. "
            "The legacy shim 'setuptools.backends.legacy:build' breaks "
            "pip editable install."
        )

    def test_legacy_build_backend_absent(self):
        """pyproject.toml must NOT contain the legacy setuptools build backend."""
        content = _read_pyproject()
        assert "setuptools.backends.legacy:build" not in content, (
            "pyproject.toml must not contain 'setuptools.backends.legacy:build'. "
            "This legacy shim causes pip install -e '.[dev]' to fail with exit code 2."
        )

    def test_wheel_in_build_requires(self):
        """pyproject.toml build-system requires must include 'wheel'."""
        content = _read_pyproject()
        assert '"wheel"' in content or "'wheel'" in content, (
            "pyproject.toml build-system.requires must include 'wheel' for "
            "editable install compatibility."
        )

    def test_setuptools_in_build_requires(self):
        """pyproject.toml build-system requires must include setuptools>=68."""
        content = _read_pyproject()
        assert "setuptools>=68" in content, (
            "pyproject.toml build-system.requires must include 'setuptools>=68'."
        )


# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------


class TestOptionalDependencies:
    def test_dev_extra_contains_pytest(self):
        """The [dev] optional-dependency group must include pytest."""
        content = _read_pyproject()
        # The dev group is defined under [project.optional-dependencies]
        assert "pytest" in content, (
            "pyproject.toml [project.optional-dependencies] dev group must "
            "include pytest so that 'pip install -e .[dev]' installs the test runner."
        )

    def test_dev_extra_pytest_version_constraint(self):
        """The [dev] group pytest entry should have a version constraint >= 7.4."""
        content = _read_pyproject()
        assert 'pytest>=7.4' in content, (
            "pyproject.toml dev extra must pin pytest>=7.4."
        )

    def test_gemini_extra_present(self):
        """The [gemini] optional-dependency group must be present."""
        content = _read_pyproject()
        assert "gemini" in content, (
            "pyproject.toml must retain the [gemini] optional-dependency group."
        )

    def test_google_genai_in_gemini_extra(self):
        """The gemini extra must include google-genai."""
        content = _read_pyproject()
        assert "google-genai" in content, (
            "pyproject.toml gemini extra must include 'google-genai>=1.0.0'."
        )


# ---------------------------------------------------------------------------
# Structural integrity
# ---------------------------------------------------------------------------


class TestPyprojectStructure:
    def test_project_name(self):
        """pyproject.toml project name must be 'cyber-immunizer'."""
        content = _read_pyproject()
        assert 'name = "cyber-immunizer"' in content, (
            "pyproject.toml must declare name = 'cyber-immunizer'."
        )

    def test_python_version_constraint(self):
        """pyproject.toml must require Python >= 3.11."""
        content = _read_pyproject()
        assert ">=3.11" in content, (
            "pyproject.toml must require Python >=3.11."
        )

    def test_pytest_ini_options_present(self):
        """The [tool.pytest.ini_options] section must be present."""
        content = _read_pyproject()
        assert "[tool.pytest.ini_options]" in content, (
            "pyproject.toml must retain [tool.pytest.ini_options] section."
        )

    def test_packages_find_section_present(self):
        """The [tool.setuptools.packages.find] section must be present."""
        content = _read_pyproject()
        assert "[tool.setuptools.packages.find]" in content, (
            "pyproject.toml must retain [tool.setuptools.packages.find] section."
        )

    def test_packages_find_includes_core(self):
        """packages.find must include 'core*'."""
        content = _read_pyproject()
        assert "core*" in content, (
            "pyproject.toml packages.find must include 'core*'."
        )

    def test_packages_find_includes_intelligence(self):
        """packages.find must include 'intelligence*'."""
        content = _read_pyproject()
        assert "intelligence*" in content, (
            "pyproject.toml packages.find must include 'intelligence*'."
        )

    def test_packages_find_includes_scripts(self):
        """packages.find must include 'scripts*'."""
        content = _read_pyproject()
        assert "scripts*" in content, (
            "pyproject.toml packages.find must include 'scripts*'."
        )
