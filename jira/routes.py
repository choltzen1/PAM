from flask import Blueprint, request, jsonify
import os
import requests
from functools import lru_cache

jira_bp = Blueprint('jira_bp', __name__)

@lru_cache(maxsize=1)
def _auto_discover_epic_link_field(base_url: str, auth_tuple: tuple[str,str], timeout: int, verify_ssl: bool):
    """Attempt to discover the Epic Link custom field id by querying /rest/api/2/field.
    Returns customfield_xxxxx or '' if not found / failure.
    """
    try:
        resp = requests.get(f"{base_url}/rest/api/2/field", auth=auth_tuple, timeout=timeout, verify=verify_ssl)
        if resp.status_code != 200:
            return ''
        for f in resp.json():
            name = (f.get('name') or '').lower()
            cid = f.get('id') or ''
            if 'epic link' in name and cid.startswith('customfield_'):
                return cid
    except Exception:
        return ''
    return ''

def _list_fields(base_url: str, auth_tuple: tuple[str,str], timeout: int, verify_ssl: bool):
    try:
        resp = requests.get(f"{base_url}/rest/api/2/field", auth=auth_tuple, timeout=timeout, verify=verify_ssl)
        if resp.status_code != 200:
            return [], f"HTTP {resp.status_code}"
        return resp.json(), None
    except Exception as e:
        return [], str(e)

def _build_config(ticket_type: str):
    if ticket_type == 'dcd':
        project_key = os.environ.get('JIRA_DCD_PROJECT', 'DCOMM')
    else:
        project_key = os.environ.get('JIRA_PROJECT', 'EFPE')
    return {
        'url': os.environ.get('JIRA_URL', 'https://t-mobile-stage.atlassian.net'),
        'username': os.environ.get('JIRA_USERNAME', ''),
        'api_token': os.environ.get('JIRA_API_TOKEN', ''),
        'project': project_key,
        'default_assignee': os.environ.get('JIRA_DEFAULT_ASSIGNEE', ''),
        'labels': os.environ.get('JIRA_LABELS', 'PAM,Promotion,BPTCR').split(','),
        'components': os.environ.get('JIRA_COMPONENTS', 'Promotion Management').split(','),
        'timeout': int(os.environ.get('JIRA_TIMEOUT', '30')),
        'verify_ssl': os.environ.get('JIRA_VERIFY_SSL', 'false').lower() == 'true'
    }

@jira_bp.route('/create_jira_ticket', methods=['POST'])
def create_jira_ticket():
    data = request.get_json() if request.is_json else request.form
    summary = data.get('summary', '')
    description = data.get('description', '')
    priority = data.get('priority', 'High')
    issue_type = data.get('issue_type', 'Task')
    parent = data.get('parent', '')
    promo_code = data.get('promo_code', '')
    ticket_type = data.get('ticket_type', 'bptcr')

    cfg = _build_config(ticket_type)
    missing = [k for k in ['url','username','api_token','project'] if not cfg[k]]
    if missing:
        return jsonify({'success': False, 'error': f'Missing JIRA config values: {", ".join(missing)}'}), 400

    fields = {
        'project': {'key': cfg['project']},
        'summary': summary,
        'description': description,
        'issuetype': {'name': issue_type},
        'priority': {'name': priority}
    }
    if cfg['labels'] and cfg['labels'][0]:
        fields['labels'] = [l.strip() for l in cfg['labels'] if l.strip()]
    if cfg['default_assignee']:
        fields['assignee'] = {'emailAddress': cfg['default_assignee']}
    
    # Parent / Epic linkage logic for DCD
    enforce_parent = os.getenv('JIRA_DCD_ENFORCE_PARENT', 'true').lower() == 'true'
    skip_parent_req = data.get('no_parent') in ('1', 'true', True)
    epic_link_field = os.getenv('JIRA_DCD_EPIC_LINK_FIELD', '').strip()  # e.g. customfield_10008 or just 10008
    # Accept bare numeric id and normalize
    if epic_link_field and epic_link_field.isdigit():
        epic_link_field = f"customfield_{epic_link_field}"
    auto_discover_epic = os.getenv('JIRA_DCD_AUTO_EPIC_LINK_DISCOVER', 'true').lower() == 'true'
    parent_fallback_story = os.getenv('JIRA_DCD_ALLOW_PARENT_FALLBACK_FOR_STORY', 'false').lower() == 'true'
    # If not provided we will only attempt a true parent (sub-task) link
    issue_type_lower = issue_type.lower()
    if parent:
        # Explicit parent supplied by client – assume caller knows it's a sub-task relationship
        fields['parent'] = {'key': parent}
    elif ticket_type == 'dcd' and enforce_parent and not skip_parent_req:
        dcd_parent = os.getenv('JIRA_DCD_CURRENT_TICKET', 'DCOMM-13037').strip()
        if dcd_parent:
            allowed_parent_statuses = [s.strip() for s in os.getenv('JIRA_DCD_ALLOWED_PARENT_STATUSES', 'In Progress,To Do,Defining,Blocked,Ready,TEST,Deploy').split(',') if s.strip()]
            force_parent = os.getenv('JIRA_DCD_FORCE_PARENT', 'true').lower() == 'true'
            try:
                cfg_parent = _build_config('dcd')
                resp_parent = requests.get(f"{cfg_parent['url']}/rest/api/2/issue/{dcd_parent}?fields=status,issuetype", auth=(cfg_parent['username'], cfg_parent['api_token']), timeout=cfg_parent['timeout'], verify=cfg_parent['verify_ssl'])
                parent_status = ''
                parent_issue_type = ''
                if resp_parent.status_code == 200:
                    pj = resp_parent.json()
                    parent_status = (pj.get('fields', {}).get('status', {}) or {}).get('name','')
                    parent_issue_type = (pj.get('fields', {}).get('issuetype', {}) or {}).get('name','')
                # Optional auto-transition if status not allowed
                auto_transition = os.getenv('JIRA_DCD_AUTO_TRANSITION', 'false').lower() == 'true'
                target_status = os.getenv('JIRA_DCD_TARGET_PARENT_STATUS', '').strip()
                attempted_transition = None
                transition_error = None
                if auto_transition and parent_status and parent_status not in allowed_parent_statuses and target_status:
                    try:
                        # Fetch transitions
                        trans_resp = requests.get(f"{cfg_parent['url']}/rest/api/2/issue/{dcd_parent}/transitions", auth=(cfg_parent['username'], cfg_parent['api_token']), timeout=cfg_parent['timeout'], verify=cfg_parent['verify_ssl'])
                        if trans_resp.status_code == 200:
                            trans_data = trans_resp.json().get('transitions', [])
                            candidate = None
                            for t in trans_data:
                                to_name = t.get('to', {}).get('name','')
                                if to_name.lower() == target_status.lower():
                                    candidate = t; break
                            if candidate:
                                tid = candidate.get('id')
                                post_resp = requests.post(f"{cfg_parent['url']}/rest/api/2/issue/{dcd_parent}/transitions", json={'transition': {'id': tid}}, auth=(cfg_parent['username'], cfg_parent['api_token']), timeout=cfg_parent['timeout'], verify=cfg_parent['verify_ssl'])
                                if post_resp.status_code in (204,200):
                                    attempted_transition = f"Transitioned parent {dcd_parent} -> {target_status}"
                                    parent_status = target_status
                                else:
                                    transition_error = f"Failed transition {tid}: {post_resp.status_code} {post_resp.text}"
                        else:
                            transition_error = f"Unable to fetch transitions: {trans_resp.status_code}"
                    except Exception as te:
                        transition_error = f"Transition exception: {te}"
                # Decide linking strategy: sub-task parent vs epic link
                if issue_type_lower in ('sub-task','subtask'):
                    # Must use parent; validate status
                    if parent_status and parent_status not in allowed_parent_statuses and not force_parent:
                        return jsonify({'success': False,
                                        'error': 'Parent status not allowed for sub-task creation',
                                        'parent': dcd_parent,
                                        'parent_status': parent_status,
                                        'allowed_statuses': allowed_parent_statuses,
                                        'attempted_transition': attempted_transition,
                                        'transition_error': transition_error,
                                        'hint': 'Transition parent or set JIRA_DCD_FORCE_PARENT=true / JIRA_DCD_AUTO_TRANSITION=true'}), 409
                    # Attach parent regardless if forcing or allowed
                    fields['parent'] = {'key': dcd_parent}
                    if parent_status and parent_status not in allowed_parent_statuses and force_parent:
                        fields['description'] = f"{fields['description']}\n\n(Forced parent {dcd_parent} in status '{parent_status}')".strip()
                else:
                    # Story/Task path: prefer Epic Link. Do NOT use parent field unless explicitly allowed.
                    effective_epic_field = epic_link_field
                    if not effective_epic_field and auto_discover_epic:
                        effective_epic_field = _auto_discover_epic_link_field(cfg_parent['url'], (cfg_parent['username'], cfg_parent['api_token']), cfg_parent['timeout'], cfg_parent['verify_ssl']) or ''
                    if effective_epic_field:
                        fields[effective_epic_field] = dcd_parent
                        if parent_status and parent_status not in allowed_parent_statuses:
                            fields['description'] = f"{fields['description']}\n\n(Linked to feature {dcd_parent} currently in status '{parent_status}')".strip()
                    else:
                        if not parent_fallback_story:
                            debug = os.getenv('DEBUG_JIRA','false').lower() == 'true'
                            extra = {}
                            if debug:
                                all_fields, ferr = _list_fields(cfg_parent['url'], (cfg_parent['username'], cfg_parent['api_token']), cfg_parent['timeout'], cfg_parent['verify_ssl'])
                                candidates = []
                                if not ferr:
                                    for f in all_fields:
                                        nm = (f.get('name') or '')
                                        if 'epic' in nm.lower():
                                            candidates.append({'id': f.get('id'), 'name': nm, 'schema': f.get('schema',{}).get('type')})
                                extra = {'candidate_epic_fields': candidates, 'fields_error': ferr}
                            return jsonify({'success': False,
                                            'error': 'Epic Link field not configured or discovered; refusing unsafe parent fallback for Story',
                                            'issue_type': issue_type,
                                            'feature_key': dcd_parent,
                                            'auto_discovery_attempted': auto_discover_epic,
                                            'hint': 'Set JIRA_DCD_EPIC_LINK_FIELD=customfield_xxxxx or enable parent fallback JIRA_DCD_ALLOW_PARENT_FALLBACK_FOR_STORY=true',
                                            **extra}), 409
                        # As last resort (legacy behavior) optionally attach parent; Jira may still reject if issue type not sub-task.
                        fields['parent'] = {'key': dcd_parent}
                        fields['description'] = f"{fields['description']}\n\n(LEGACY FALLBACK: used parent field for non-subtask; configure Epic Link field to fix)".strip()
            except Exception as parent_err:
                fields['description'] = f"{fields['description']}\n\n(Parent/Epic lookup failed: {parent_err})".strip()

    # R2D2 team custom field logic - using correct team IDs
    if cfg['project'] == 'CPO':
        fields['customfield_10279'] = {'id': os.getenv('JIRA_R2D2_TEAM_ID', '14013')}
    elif cfg['project'] == 'DCOMM':
        fields['customfield_10279'] = {'id': os.getenv('JIRA_DCD_R2D2_TEAM_ID', '12793')}

    if promo_code:
        fields['description'] = f"{fields['description']}\n\nPromotion Code: {promo_code}".strip()

    payload = {'fields': fields}
    try:
        # Support deferred Epic Link setting if the field is not present on the create screen.
        epic_field_attempted = None
        for k in list(fields.keys()):
            if k.startswith('customfield_') and k != 'customfield_10279':  # crude heuristic; we'll record which epic field we tried
                # We only track the epic link field we just added (earlier logic ensures only one new custom field besides team id)
                if k != 'customfield_10279':
                    epic_field_attempted = k
        defer_allowed = os.getenv('JIRA_DCD_EPIC_LINK_DEFER_IF_UNSET_SCREEN', 'true').lower() == 'true'
        epic_parent_value = None
        if epic_field_attempted:
            epic_parent_value = fields.get(epic_field_attempted)

        def _create(payload_fields):
            return requests.post(
                f"{cfg['url']}/rest/api/2/issue/",
                json={'fields': payload_fields},
                auth=(cfg['username'], cfg['api_token']),
                timeout=cfg['timeout'],
                verify=cfg['verify_ssl'],
                headers={'Accept': 'application/json', 'Content-Type': 'application/json'}
            )

        resp = _create(fields)
        if resp.status_code == 201:
            data = resp.json()
            ticket_key = data['key']
            return jsonify({'success': True, 'ticket_key': ticket_key, 'ticket_url': f"{cfg['url']}/browse/{ticket_key}"})

        # If 400 AND epic link field complained about not on screen, try deferred flow
        deferred = False
        update_applied = False
        update_error = None
        if resp.status_code == 400 and epic_field_attempted and defer_allowed:
            epic_numeric = epic_field_attempted.split('_')[-1]
            j = None
            try:
                j = resp.json()
            except Exception:
                j = {}
            errors_block = (j or {}).get('errors') or {}
            complaint = errors_block.get(epic_numeric) or errors_block.get(epic_field_attempted)
            if complaint and 'cannot be set' in complaint.lower():
                # Retry without epic link on create
                original_complaint = complaint
                fields_no_epic = {fk: fv for fk, fv in fields.items() if fk != epic_field_attempted}
                # Add marker note to description
                desc = fields_no_epic.get('description', '')
                fields_no_epic['description'] = f"{desc}\n\n(Epic Link deferred: field {epic_field_attempted} not on create screen)".strip()
                resp2 = _create(fields_no_epic)
                if resp2.status_code == 201:
                    deferred = True
                    data2 = resp2.json()
                    ticket_key = data2['key']
                    # Attempt to update epic link via edit (may still fail if not on edit screen either)
                    if epic_parent_value:
                        try:
                            put_resp = requests.put(
                                f"{cfg['url']}/rest/api/2/issue/{ticket_key}",
                                json={'fields': {epic_field_attempted: epic_parent_value}},
                                auth=(cfg['username'], cfg['api_token']),
                                timeout=cfg['timeout'],
                                verify=cfg['verify_ssl'],
                                headers={'Accept': 'application/json', 'Content-Type': 'application/json'}
                            )
                            if put_resp.status_code in (200, 204):
                                update_applied = True
                            else:
                                update_error = f"Update failed {put_resp.status_code}: {put_resp.text}"[:500]
                        except Exception as ue:
                            update_error = f"Update exception: {ue}"[:300]
                    result = {
                        'success': True,
                        'ticket_key': ticket_key,
                        'ticket_url': f"{cfg['url']}/browse/{ticket_key}",
                        'epic_link_deferred': deferred,
                        'epic_link_update_applied': update_applied,
                        'epic_link_update_error': update_error,
                        'original_epic_error': original_complaint,
                        'hint': 'Add Epic Link field to the create/edit screen to avoid deferral' if deferred else None
                    }
                    return jsonify(result)
                else:
                    # Return both original and retry errors
                    return jsonify({'success': False,
                                    'error': f'JIRA create failed (with and without epic link). First: {resp.status_code}; Retry: {resp2.status_code}',
                                    'first_body': resp.text[:800],
                                    'retry_body': resp2.text[:800],
                                    'epic_field': epic_field_attempted,
                                    'epic_numeric': epic_numeric})

        return jsonify({'success': False, 'error': f'JIRA create failed {resp.status_code}: {resp.text}'})
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'JIRA request timed out'})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'JIRA connection error'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {e}'})

@jira_bp.route('/jira/parent_status', methods=['GET'])
def jira_parent_status():
    """Diagnostic endpoint to inspect current DCD parent issue status & transitions.

    Query params:
      showTransitions=1  -> include available transitions (names & ids)
    """
    ticket_type = request.args.get('ticket_type','dcd')
    if ticket_type != 'dcd':
        return jsonify({'success': False, 'error': 'Only dcd supported for this diagnostic'}), 400
    parent_key = os.getenv('JIRA_DCD_CURRENT_TICKET','').strip()
    if not parent_key:
        return jsonify({'success': False, 'error': 'JIRA_DCD_CURRENT_TICKET not set'}), 400
    cfg = _build_config('dcd')
    try:
        resp = requests.get(f"{cfg['url']}/rest/api/2/issue/{parent_key}?fields=status,issuetype", auth=(cfg['username'], cfg['api_token']), timeout=cfg['timeout'], verify=cfg['verify_ssl'])
        if resp.status_code != 200:
            return jsonify({'success': False, 'error': f'Fetch failed {resp.status_code}', 'body': resp.text}), 502
        data = resp.json()
        status_name = (data.get('fields',{}).get('status',{}) or {}).get('name','')
        issue_type = (data.get('fields',{}).get('issuetype',{}) or {}).get('name','')
        allowed = [s.strip() for s in os.getenv('JIRA_DCD_ALLOWED_PARENT_STATUSES', 'In Progress,To Do,Defining,Blocked,Ready,TEST,Deploy').split(',') if s.strip()]
        result = {
            'success': True,
            'parent': parent_key,
            'parent_issue_type': issue_type,
            'status': status_name,
            'allowed_statuses': allowed
        }
        if request.args.get('showTransitions') == '1':
            trans_resp = requests.get(f"{cfg['url']}/rest/api/2/issue/{parent_key}/transitions", auth=(cfg['username'], cfg['api_token']), timeout=cfg['timeout'], verify=cfg['verify_ssl'])
            if trans_resp.status_code == 200:
                result['transitions'] = [
                    {'id': t.get('id'), 'name': t.get('name'), 'to_status': t.get('to',{}).get('name')} for t in trans_resp.json().get('transitions',[])
                ]
        return jsonify(result)
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Timeout fetching parent'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {e}'})

@jira_bp.route('/jira/fields', methods=['GET'])
def jira_fields():
    """List all Jira fields or filter for names containing a substring (?q=epic)."""
    cfg = _build_config('dcd')
    q = (request.args.get('q') or '').lower().strip()
    fields, ferr = _list_fields(cfg['url'], (cfg['username'], cfg['api_token']), cfg['timeout'], cfg['verify_ssl'])
    if ferr:
        return jsonify({'success': False, 'error': ferr}), 502
    slim = []
    for f in fields:
        name = f.get('name') or ''
        if q and q not in name.lower():
            continue
        slim.append({'id': f.get('id'), 'name': name, 'type': f.get('schema',{}).get('type'), 'custom': f.get('custom', False)})
    return jsonify({'success': True, 'count': len(slim), 'fields': slim})

@jira_bp.route('/jira/epic_link_diagnose', methods=['GET'])
def jira_epic_link_diagnose():
    """Diagnose Epic Link usability differences between default and DCD project.

    Returns:
      - env_epic_field: value of JIRA_DCD_EPIC_LINK_FIELD (normalized)
      - dcd_create_meta_has_epic: bool if field is on DCD Story create screen
      - default_create_meta_has_epic: bool if field is on default project Story create screen
      - dcd_fields_sample / default_fields_sample: subset of field ids for quick comparison
      - suggestions: textual guidance
    """
    base_cfg_default = _build_config('bptcr')  # uses JIRA_PROJECT
    base_cfg_dcd = _build_config('dcd')        # uses JIRA_DCD_PROJECT
    epic_env = os.getenv('JIRA_DCD_EPIC_LINK_FIELD','').strip()
    if epic_env and epic_env.isdigit():
        epic_env = f"customfield_{epic_env}"
    issue_type = request.args.get('issueType','Story')
    timeout = base_cfg_dcd['timeout']
    verify = base_cfg_dcd['verify_ssl']
    auth_default = (base_cfg_default['username'], base_cfg_default['api_token'])
    auth_dcd = (base_cfg_dcd['username'], base_cfg_dcd['api_token'])

    def fetch_meta(project_key, auth_pair):
        try:
            url = f"{base_cfg_dcd['url']}/rest/api/2/issue/createmeta"  # same base URL
            params = {
                'projectKeys': project_key,
                'issuetypeNames': issue_type,
                'expand': 'projects.issuetypes.fields'
            }
            r = requests.get(url, params=params, auth=auth_pair, timeout=timeout, verify=verify)
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}: {r.text[:300]}"
            return r.json(), None
        except Exception as e:
            return None, str(e)

    meta_dcd, err_dcd = fetch_meta(base_cfg_dcd['project'], auth_dcd)
    meta_default, err_def = fetch_meta(base_cfg_default['project'], auth_default)

    def extract_fields(meta_json):
        if not meta_json:
            return {}, []
        try:
            projects = meta_json.get('projects', [])
            if not projects:
                return {}, []
            itypes = projects[0].get('issuetypes', [])
            for it in itypes:
                if (it.get('name') or '').lower() == issue_type.lower():
                    fields = it.get('fields', {})
                    return fields, list(fields.keys())
        except Exception:
            return {}, []
        return {}, []

    dcd_fields_map, dcd_field_ids = extract_fields(meta_dcd)
    def_fields_map, def_field_ids = extract_fields(meta_default)

    has_epic_dcd = epic_env in dcd_field_ids if epic_env else False
    has_epic_def = epic_env in def_field_ids if epic_env else False

    sample_limit = 25
    def summarize(ids):
        return ids[:sample_limit]

    suggestions = []
    if not epic_env:
        suggestions.append('Set JIRA_DCD_EPIC_LINK_FIELD to the customfield id for Epic Link.')
    else:
        if not has_epic_dcd:
            suggestions.append(f"Add field {epic_env} to the DCD project's Story Create screen (Project Settings -> Screens).")
        if has_epic_dcd and not has_epic_def:
            suggestions.append('Field appears on DCD but not default project; verify you are comparing correct projects.')
        if not has_epic_def and not has_epic_dcd:
            suggestions.append('Field absent on both create screens: confirm screen scheme or global context for Epic Link.')

    return jsonify({
        'success': True,
        'env_epic_field': epic_env,
        'issue_type': issue_type,
        'dcd_project': base_cfg_dcd['project'],
        'default_project': base_cfg_default['project'],
        'dcd_create_meta_has_epic': has_epic_dcd,
        'default_create_meta_has_epic': has_epic_def,
        'dcd_fields_sample': summarize(dcd_field_ids),
        'default_fields_sample': summarize(def_field_ids),
        'dcd_meta_error': err_dcd,
        'default_meta_error': err_def,
        'suggestions': suggestions
    })
