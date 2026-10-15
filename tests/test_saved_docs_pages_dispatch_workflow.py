from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-saved-google-docs-reports.yml"


def step_body(name: str) -> str:
    source = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n(?P<body>.*?)(?=^      - name: |\Z)",
        source,
    )
    if not match:
        raise AssertionError(f"workflow step missing: {name}")
    return match.group("body")


class SavedDocsPagesDispatchWorkflowTests(unittest.TestCase):
    def test_dispatch_permission_is_scoped_to_workflow_dispatch(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(source, r"(?m)^permissions:\n  contents: write\n  actions: write$")
        self.assertIn("workflow_dispatch:", source)

    def test_noop_import_does_not_dispatch_pages(self) -> None:
        persist = step_body("Persist actual Docs-derived changes to main and request Pages deploy")
        self.assertIn("id: persist", persist)
        no_change = persist.index('echo "changed=false" >> "$GITHUB_OUTPUT"')
        noop_exit = persist.index("exit 0", no_change)
        push = persist.index("git push origin HEAD:main")
        changed = persist.index('echo "changed=true" >> "$GITHUB_OUTPUT"')
        self.assertLess(no_change, noop_exit)
        self.assertLess(push, changed)

        dispatch = step_body("Dispatch Pages deployment for the committed archive")
        self.assertRegex(dispatch, r"(?m)^        if: steps\.persist\.outputs\.changed == 'true'$")

    def test_dispatch_uses_masked_github_token_without_printing_it(self) -> None:
        dispatch = step_body("Dispatch Pages deployment for the committed archive")
        self.assertIn("GH_TOKEN: ${{ github.token }}", dispatch)
        self.assertIn("/actions/workflows/deploy-pages.yml/dispatches", dispatch)
        self.assertIn('--data \'{"ref":"main"}\'', dispatch)
        self.assertIn('"Authorization: Bearer ${GH_TOKEN}"', dispatch)
        self.assertNotRegex(dispatch, r"(?im)^\s*(?:echo|printf).*\$\{?GH_TOKEN")

    def test_dispatch_is_separate_from_publication_eligibility(self) -> None:
        dispatch = step_body("Dispatch Pages deployment for the committed archive")
        self.assertNotIn("report_status", dispatch)
        self.assertNotIn("PUBLISHED", dispatch)
        self.assertNotIn("publication-receipts", dispatch)


if __name__ == "__main__":
    unittest.main()
