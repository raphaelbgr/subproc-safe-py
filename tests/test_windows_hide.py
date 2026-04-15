"""Tests for _win_silent_kwargs() — Rule 2: Windows console suppression."""
import subprocess
import sys
import unittest
import unittest.mock


class TestWinSilentKwargs(unittest.TestCase):
    def _import_fn(self):
        from subproc_safe._core import _win_silent_kwargs
        return _win_silent_kwargs

    def test_win32_returns_creationflags_and_startupinfo(self):
        """On win32, must return creationflags=CREATE_NO_WINDOW and startupinfo with SW_HIDE."""
        _win_silent_kwargs = self._import_fn()

        # Patch sys.platform to win32 and re-evaluate via direct call with mocked platform
        with unittest.mock.patch('subproc_safe._core.sys') as mock_sys, \
             unittest.mock.patch('subproc_safe._core.subprocess') as mock_subprocess:

            mock_sys.platform = 'win32'

            # Set up mock STARTUPINFO with writable attributes
            mock_si = unittest.mock.MagicMock()
            mock_si.dwFlags = 0
            mock_si.wShowWindow = None
            mock_subprocess.STARTUPINFO.return_value = mock_si
            mock_subprocess.STARTF_USESHOWWINDOW = subprocess.STARTF_USESHOWWINDOW if sys.platform == 'win32' else 1

            result = _win_silent_kwargs()

        self.assertIn('creationflags', result)
        self.assertEqual(result['creationflags'], 0x08000000)
        self.assertIn('startupinfo', result)
        self.assertEqual(result['startupinfo'].wShowWindow, 0)

    def test_non_win32_returns_empty(self):
        """On non-win32, must return empty dict."""
        _win_silent_kwargs = self._import_fn()

        with unittest.mock.patch('subproc_safe._core.sys') as mock_sys:
            mock_sys.platform = 'linux'
            result = _win_silent_kwargs()

        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()
