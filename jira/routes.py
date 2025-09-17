from flask import Blueprint, request, jsonify
import os
import requests

jira_bp = Blueprint('jira_bp', __name__)

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
    if parent:
        fields['parent'] = {'key': parent}

    # R2D2 team custom field logic
    if cfg['project'] == 'CPO':
        fields['customfield_10279'] = {'id': os.getenv('JIRA_R2D2_TEAM_ID', '14013')}
    elif cfg['project'] == 'DCOMM':
        fields['customfield_10279'] = {'id': os.getenv('JIRA_DCD_R2D2_TEAM_ID', '12762')}

    if promo_code:
        fields['description'] = f"{fields['description']}\n\nPromotion Code: {promo_code}".strip()

    payload = {'fields': fields}
    try:
        resp = requests.post(f"{cfg['url']}/rest/api/2/issue/", json=payload, auth=(cfg['username'], cfg['api_token']), timeout=cfg['timeout'], verify=cfg['verify_ssl'], headers={'Accept':'application/json','Content-Type':'application/json'})
        if resp.status_code == 201:
            data = resp.json()
            ticket_key = data['key']
            return jsonify({'success': True, 'ticket_key': ticket_key, 'ticket_url': f"{cfg['url']}/browse/{ticket_key}"})
        return jsonify({'success': False, 'error': f'JIRA create failed {resp.status_code}: {resp.text}'})
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'JIRA request timed out'})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'JIRA connection error'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {e}'})
