"""Script temporaire pour vérifier les tests - exécuter avec: python run_tests_check.py"""

import unittest
import sys
import io
import pathlib

patterns = sys.argv[1:] or ["test_lan_networking.py"]

all_results = []
all_output = []

for pattern in patterns:
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern=pattern)
    buf = io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=2)
    result = runner.run(suite)
    all_output.append(f"=== {pattern} ===\n" + buf.getvalue())
    all_results.append(result)

full_output = "\n".join(all_output)
total_run = sum(r.testsRun for r in all_results)
total_fail = sum(len(r.failures) for r in all_results)
total_err = sum(len(r.errors) for r in all_results)
summary = f"\n{'='*60}\nTOTAL: {total_run} tests | Failures: {total_fail} | Errors: {total_err}\n"

out_path = pathlib.Path("test_results.txt")
out_path.write_text(full_output + summary, encoding="utf-8")
print(summary)
sys.exit(0 if all(r.wasSuccessful() for r in all_results) else 1)
