"""Exercise the actual PowerShell wrapper with local stubs; no gateway/VMS calls."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(shutil.which('powershell'), 'Windows PowerShell required')
class WrapperTests(unittest.TestCase):
    def run_wrapper(self, coverage, stale_exit):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root/'scripts'
            scripts.mkdir()
            wrapper = scripts/'reliability_diagnostic_execute.ps1'
            wrapper.write_bytes((REPO/'scripts'/wrapper.name).read_bytes())
            (scripts/'reliability_availability.ps1').write_text(
                'param($EvaluationRoot,$PlanPath)\n' + coverage)
            (scripts/'reliability_diagnostic_execute.py').write_text(
                "from pathlib import Path\nPath('executor-entered').write_text('stub only')\n")
            command = (
                'function Join-Path { param($Path,$ChildPath) '
                "if ($ChildPath -eq '.venv/Scripts/python.exe') { "
                + ps_quote(sys.executable) + ' } else { '
                'Microsoft.PowerShell.Management\\Join-Path -Path $Path -ChildPath $ChildPath } }; '
                '$global:LASTEXITCODE = ' + str(stale_exit) + '; & ' + ps_quote(wrapper)
            )
            result = subprocess.run(['powershell','-NoProfile','-Command',command],
                                    capture_output=True,text=True)
            return result, (root/'executor-entered').exists()

    def test_successful_coverage_ignores_stale_native_exit(self):
        result, entered = self.run_wrapper("Write-Host 'Verified stub coverage'",7)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(entered,result.stdout + result.stderr)

    def test_coverage_exception_blocks_executor(self):
        result, entered = self.run_wrapper("throw 'Coverage unavailable'",0)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(entered)
        self.assertIn('Coverage unavailable',result.stderr)
