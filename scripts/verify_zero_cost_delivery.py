"""Offline cost gate. No secrets, credentials, HTTP, or paid SDK imports."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
API_ENDPOINT = re.compile(r'https?://(?:api\.(?:openai|anthropic|mistral|cohere|x)\.\w+|generativelanguage\.googleapis\.com)')


def check(root: Path = ROOT, *, production: bool = False) -> dict:
    policy = json.loads((root / 'config/report_delivery_policy.json').read_text(encoding='utf-8-sig'))
    reasons = []
    if any(policy.get(k) is not False for k in (
        'paidApiCallsAllowed', 'newUsageBillingAllowed', 'newRecurringCostAllowed', 'creditCardRequired'
    )):
        reasons.append('ZERO_COST_POLICY_REQUIRED')
    if policy.get('mode') != 'shadow' or policy.get('productionOwner') != 'legacy' or policy.get('productionAdapter') is not None:
        reasons.append('PRODUCTION_ADAPTER_NOT_AUTHORIZED')
    endpoints = []
    for folder in ('scripts', 'apps-script', '.github/workflows'):
        for p in sorted((root / folder).rglob('*')):
            if not p.is_file() or p.suffix not in ('.py', '.js', '.gs', '.yml', '.yaml', '.sh'):
                continue
            text = p.read_text(encoding='utf-8-sig')
            if not API_ENDPOINT.search(text):
                continue
            # Retained historical API workflows must skip EVERY job, before checkout/secrets.
            jobs = re.findall(r'^  [\w-]+:\s*\n(.*?)(?=^  [\w-]+:|\Z)', text.split('\njobs:', 1)[-1], re.M | re.S) if '\njobs:' in text else []
            disabled = p.suffix in ('.yml', '.yaml') and bool(jobs) and all(
                re.match(r'    if: \$\{\{ false \}\}\s*(?:#.*)?\n', job) for job in jobs)
            endpoints.append({'path':p.relative_to(root).as_posix(), 'allJobsDisabled':disabled})
            if not disabled:
                reasons.append('REACHABLE_AI_API_ENDPOINT:' + p.relative_to(root).as_posix())
    if production:
        reasons.append('BLOCKED_COST_UNVERIFIED: production quotas, billing, data rights and runtime ownership need independent evidence')
    return {'changeId':policy['changeId'], 'scope':'LOCAL_SHADOW_ONLY',
            'NEW_RECURRING_COST':0, 'NEW_USAGE_BILLING':0, 'NEW_PAID_API_CALLS':0,
            'NEW_CREDIT_CARD_REQUIRED':False, 'newDependencies':[],
            'status':'PASS_LOCAL_ONLY' if not reasons else 'BLOCKED_COST_UNVERIFIED',
            'reasons':reasons, 'retainedApiWorkflows':endpoints}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--production', action='store_true')
    args = ap.parse_args()
    result = check(production=args.production)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS_LOCAL_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
