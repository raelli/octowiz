"""Tests for path_guard.validate_cwd.

Covers the two security properties that must match policy.js (Node.js canonical):
  1. Empty/unset OCTOWIZ_ALLOWED_ROOTS → deny-all (not allow-all).
  2. Root paths resolved via os.path.realpath() before comparison —
     symlinked roots are canonicalized, preventing bypass.
"""
import os
import tempfile
import unittest
from unittest.mock import patch


class TestValidateCwdDenyAll(unittest.TestCase):
    """Empty/unset allowlist must deny, not allow."""

    def test_unset_allowed_roots_raises(self):
        from path_guard import validate_cwd
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                validate_cwd("/tmp")
        self.assertIn("not set", str(ctx.exception).lower())

    def test_empty_string_allowed_roots_raises(self):
        from path_guard import validate_cwd
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": ""}):
            with self.assertRaises(ValueError):
                validate_cwd("/tmp")

    def test_whitespace_only_allowed_roots_raises(self):
        from path_guard import validate_cwd
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "  :  "}):
            with self.assertRaises(ValueError):
                validate_cwd("/tmp")


class TestValidateCwdSymlinkResolution(unittest.TestCase):
    """Root paths must be resolved before comparison."""

    def test_symlinked_root_matches_real_cwd(self):
        """A symlinked root entry should still allow the real target path."""
        from path_guard import validate_cwd
        with tempfile.TemporaryDirectory() as real_dir:
            link_dir = real_dir + "-link"
            try:
                os.symlink(real_dir, link_dir)
                # Root given as symlink — cwd is the real path
                with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": link_dir}):
                    result = validate_cwd(real_dir)
                self.assertTrue(result.startswith("/"))
            finally:
                if os.path.islink(link_dir):
                    os.unlink(link_dir)

    def test_symlinked_cwd_matched_against_real_root(self):
        """A symlinked cwd should resolve to real path before comparison."""
        from path_guard import validate_cwd
        with tempfile.TemporaryDirectory() as real_dir:
            link_dir = real_dir + "-cwdlink"
            try:
                os.symlink(real_dir, link_dir)
                with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": real_dir}):
                    result = validate_cwd(link_dir)
                self.assertEqual(result, os.path.realpath(link_dir))
            finally:
                if os.path.islink(link_dir):
                    os.unlink(link_dir)


class TestValidateCwdBasicContract(unittest.TestCase):
    """Core allow/deny contract."""

    def test_relative_path_raises(self):
        from path_guard import validate_cwd
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/allowed"}):
            with self.assertRaises(ValueError) as ctx:
                validate_cwd("relative/path")
        self.assertIn("absolute", str(ctx.exception))

    def test_path_within_root_allowed(self):
        from path_guard import validate_cwd
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "project")
            os.makedirs(sub)
            with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": d}):
                result = validate_cwd(sub)
            self.assertEqual(result, os.path.realpath(sub))

    def test_path_outside_root_denied(self):
        from path_guard import validate_cwd
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/allowed"}):
            with self.assertRaises(ValueError) as ctx:
                validate_cwd("/other/path")
        self.assertIn("allowed root", str(ctx.exception))

    def test_root_path_itself_allowed(self):
        from path_guard import validate_cwd
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": d}):
                result = validate_cwd(d)
            self.assertEqual(result, os.path.realpath(d))

    def test_multiple_roots_any_match_allowed(self):
        from path_guard import validate_cwd
        with tempfile.TemporaryDirectory() as d1:
            with tempfile.TemporaryDirectory() as d2:
                with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": f"{d1}:{d2}"}):
                    result = validate_cwd(d2)
                self.assertEqual(result, os.path.realpath(d2))
