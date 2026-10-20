"""Read-only XProtect REST client; Basic-user IDP authentication, verified TLS."""
from datetime import datetime
import getpass
import json
import os
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from uuid import UUID

from .store import interval


class XProtectError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise XProtectError('XProtect redirect refused; use the correct HTTPS API Gateway URL')


class XProtect:
    def __init__(self, base, ca_file=None):
        parts = urlsplit(base)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.path not in ('', '/') or parts.query or parts.fragment):
            raise ValueError('XProtect URL must be an HTTPS origin without credentials')
        self.base = base.rstrip('/')
        self.token = None
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)))

    def _request(self, path, form=None):
        headers = {'Accept': 'application/json'}
        data = None
        if form is not None:
            data = urlencode(form).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        elif self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        try:
            with self.opener.open(Request(self.base + path, data=data, headers=headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            raise XProtectError(f'XProtect request failed (HTTP {exc.code}); check permissions and API availability') from None
        except (URLError, TimeoutError, ValueError):
            raise XProtectError('XProtect connection, certificate or JSON response failed') from None

    def authenticate(self):
        self.token = os.getenv('XPROTECT_TOKEN')
        if not self.token:
            username = os.getenv('XPROTECT_USERNAME') or input('XProtect Basic username: ')
            password = os.getenv('XPROTECT_PASSWORD') or getpass.getpass('XProtect Basic password: ')
            response = self._request('/API/IDP/connect/token', {
                'grant_type': 'password', 'client_id': 'GrantValidatorClient',
                'username': username, 'password': password,
            })
            self.token = response.get('access_token') if isinstance(response, dict) else None
        if not isinstance(self.token, str) or not self.token.strip():
            raise XProtectError('IDP returned no access token')

    def collection(self, resource, start, end, camera_id=None):
        if resource not in {'alarms', 'events'}:
            raise ValueError('Only alarms and events can be read')
        start, end = interval(start, end)
        filters = {'time': f"gt:'{start}',lt:'{end}'", 'size': 200}
        if camera_id:
            if resource == 'events':
                raise ValueError('Event retrieval supports time filtering only')
            filters['source.id'] = f"equals:'cameras/{UUID(camera_id)}'"
        items = []
        # Ignore server-supplied next URLs so bearer tokens cannot leave this origin.
        for page in range(100):
            response = self._request('/api/rest/v1/' + resource + '?' + urlencode({**filters, 'page': page}))
            if not isinstance(response, dict) or not isinstance(response.get('array'), list):
                raise XProtectError('Unexpected collection shape; no association made')
            batch = response['array']
            if any(not isinstance(item, dict) for item in batch):
                raise XProtectError('Unexpected collection item; no association made')
            items.extend(batch)
            links = response.get('_links') or {}
            if not isinstance(links, dict):
                raise XProtectError('Unexpected paging metadata; no association made')
            if len(batch) < 200 and not links.get('next'):
                return items
        raise XProtectError('Pagination limit reached; incomplete results cannot be associated')


def alarm_candidates(alarms, camera_id, alarm_name, start, end):
    """Camera/time/name are candidates only, never proof of a summary-to-alarm link."""
    camera_id = str(UUID(camera_id))
    start, end = (datetime.fromisoformat(v.replace('Z', '+00:00')) for v in interval(start, end))
    candidates = []
    for alarm in alarms:
        if isinstance(alarm.get('source'), str) and alarm['source'].lower() in {camera_id, 'cameras/' + camera_id} and alarm.get('name') == alarm_name:
            try:
                alarm_id = str(UUID(alarm['id']))
                triggered = datetime.fromisoformat(alarm['time'].replace('Z', '+00:00'))
                if not start < triggered < end:
                    continue
            except (ValueError, KeyError, TypeError, AttributeError):
                raise XProtectError('Invalid alarm identity or time; no association made') from None
            candidates.append({**{k: alarm[k] for k in ('source', 'time', 'name')}, 'id': alarm_id})
    return candidates


def associate(store, client, case_id, start, end, alarm_name, alarm_id=None, note=None):
    case = store.case(case_id)
    alarms = client.collection('alarms', start, end, case['camera_id'])
    candidates = alarm_candidates(alarms, case['camera_id'], alarm_name, start, end)
    ids = {c['id'] for c in candidates}
    if None in ids or len(ids) != len(candidates):
        raise XProtectError('Invalid or duplicate alarm IDs; no association made')
    status = 'ambiguous' if len(candidates) > 1 else 'unconfirmed' if candidates else 'not_found'
    # shortcut: no verified shared correlation ID; retain operator confirmation until the VM proves one.
    linked = None
    if alarm_id:
        if len(candidates) != 1 or alarm_id not in ids or not note or not note.strip():
            store.record_alarm_check(case_id, status, None, {'candidates': candidates, 'link_rejected': True, 'window': interval(start, end)})
            raise ValueError('Link requires exactly one matching alarm and an operator verification note')
        linked, status = str(UUID(alarm_id)), 'operator_confirmed'
    detail = {'window': interval(start, end), 'alarm_name': alarm_name, 'candidates': candidates, 'operator_note': note}
    store.record_alarm_check(case_id, status, linked, detail)
    return {'status': status, 'alarm_id': linked, **detail}
