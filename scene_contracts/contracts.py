"""Versioned contracts and conservative, format-strict assessment."""
import json
from pathlib import Path
import re

DEFAULT_CONTRACTS = Path(__file__).resolve().parent.parent / 'contracts'


def load_contracts(directory=DEFAULT_CONTRACTS):
    contracts = []
    for path in sorted(Path(directory).glob('*.json')):
        c = json.loads(path.read_text(encoding='utf-8'))
        for key in ('id', 'version', 'name', 'expected_condition', 'assessment_prompt', 'operator_action'):
            if not isinstance(c.get(key), str) or not c[key].strip():
                raise ValueError(f'Invalid contract {path.name}: {key}')
        for key in ('camera_names', 'response_fields', 'positive_evidence_fields'):
            if not isinstance(c.get(key), list) or not c[key] or any(not isinstance(v, str) or not v.strip() for v in c[key]):
                raise ValueError(f'Invalid contract {path.name}: {key}')
            if len(c[key]) != len(set(c[key])):
                raise ValueError(f'Duplicate contract entries: {key}')
        if (not isinstance(c.get('outcomes'), dict) or set(c['outcomes'].values()) != {'positive', 'negative', 'uncertain'}
                or any(not re.fullmatch(r'[A-Z][A-Z0-9_]*', k) for k in c['outcomes'])):
            raise ValueError('Contract outcomes must map explicit tokens to positive, negative and uncertain')
        if (any(not re.fullmatch(r'[A-Z][A-Z0-9_]*', f) or f == 'DECISION' for f in c['response_fields'])
                or not set(c['positive_evidence_fields']) <= set(c['response_fields'])):
            raise ValueError('Invalid contract response fields')
        if any(old['id'] == c['id'] for old in contracts):
            raise ValueError('Duplicate contract ID')
        if 'gateway_prompt_title' in c and (not isinstance(c['gateway_prompt_title'], str) or not c['gateway_prompt_title'].strip()):
            raise ValueError('Invalid saved prompt title')
        contracts.append(c)
    return contracts


def assess(contract, item):
    uncertain = {'outcome': 'uncertain', 'decision': None, 'evidence': {}, 'reason': 'Malformed or incomplete response'}
    if item.get('Progress') != 'Completed' or not isinstance(item.get('Response'), str):
        return uncertain
    fields = {}
    for line in item['Response'].strip().splitlines():
        match = re.fullmatch(r'([A-Z][A-Z0-9_]*):[ \t]*(\S.*)', line)
        if not match or match[1] in fields:
            return uncertain
        fields[match[1]] = match[2].strip()
    if set(fields) != {'DECISION', *contract['response_fields']}:
        return uncertain
    decision = fields.pop('DECISION')
    outcome = contract['outcomes'].get(decision)
    if outcome is None:
        return uncertain
    # A second token in prose can also trigger the existing keyword gateway rule.
    if any(re.search(r'\b' + re.escape(token) + r'\b', value)
           for token in contract['outcomes'] for value in fields.values()):
        return uncertain
    reason = 'Explicit assessment; operator verification required'
    # shortcut: this checks evidence text, not footage truth; calibrate against captured VM responses before automation.
    if outcome == 'positive' and any(
        re.match(r'(?:none(?: established| visible)?|unknown|uncertain|n/?a|not (?:established|visible|available)|no evidence|no (?:visible |new )?(?:change|damage)|<.*>|\.{3}|-)(?:[.!]|$|\s)', fields[f], re.I)
        for f in contract['positive_evidence_fields']
    ):
        outcome, reason = 'uncertain', 'Positive decision lacks explicit supporting evidence'
    return {'outcome': outcome, 'decision': decision, 'evidence': fields, 'reason': reason}
