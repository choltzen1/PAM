#!/usr/bin/env python3
"""
Test script to find the correct team ID for Ops Engineering
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# JIRA configuration
JIRA_URL = os.environ.get('JIRA_URL', 'https://t-mobile.atlassian.net')
JIRA_USERNAME = os.environ.get('JIRA_USERNAME', '')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN', '')
JIRA_DCD_PROJECT = os.environ.get('JIRA_DCD_PROJECT', 'DCOMM')
JIRA_DCD_CURRENT_TICKET = os.environ.get('JIRA_DCD_CURRENT_TICKET', 'DCOMM-15956')

# Team IDs to test
team_ids = {
    '12756': 'Current setting',
    '12762': 'Alternative 1', 
    '12748': 'Alternative 2',
    '12793': 'Alternative 3',
    '12778': 'Alternative 4'
}

def test_team_id(team_id, description):
    """Test creating a JIRA ticket with specific team ID"""
    print(f"\nTesting Team ID {team_id} ({description})...")
    
    fields = {
        'project': {'key': JIRA_DCD_PROJECT},
        'summary': f'TEST - Team ID {team_id} validation',
        'description': f'This is a test ticket to validate team ID {team_id}. Please delete.',
        'issuetype': {'name': 'Task'},
        'priority': {'name': 'Low'},
        'parent': {'key': JIRA_DCD_CURRENT_TICKET},
        'customfield_10279': {'id': team_id}  # R2D2 team field
    }
    
    payload = {'fields': fields}
    
    try:
        response = requests.post(
            f"{JIRA_URL}/rest/api/2/issue/",
            json=payload,
            auth=(JIRA_USERNAME, JIRA_API_TOKEN),
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            ticket_key = data['key']
            print(f"✅ SUCCESS: Created ticket {ticket_key} with team ID {team_id}")
            return ticket_key
        else:
            print(f"❌ FAILED: {response.status_code}")
            error_text = response.text[:200] + "..." if len(response.text) > 200 else response.text
            print(f"   Error: {error_text}")
            return None
            
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)[:100]}")
        return None

def get_ticket_details(ticket_key):
    """Get details about a created ticket to see the team name"""
    try:
        response = requests.get(
            f"{JIRA_URL}/rest/api/2/issue/{ticket_key}",
            auth=(JIRA_USERNAME, JIRA_API_TOKEN),
            headers={'Accept': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            team_field = data['fields'].get('customfield_10279')
            if team_field:
                team_name = team_field.get('value', 'Unknown')
                print(f"   Team name: {team_name}")
                return team_name
        
    except Exception as e:
        print(f"   Could not get ticket details: {e}")
    
    return None

if __name__ == "__main__":
    print("Testing JIRA Team IDs for Ops Engineering...")
    print(f"JIRA URL: {JIRA_URL}")
    print(f"Project: {JIRA_DCD_PROJECT}")
    print(f"Parent: {JIRA_DCD_CURRENT_TICKET}")
    print("=" * 60)
    
    successful_tickets = []
    
    for team_id, description in team_ids.items():
        ticket_key = test_team_id(team_id, description)
        if ticket_key:
            successful_tickets.append((ticket_key, team_id))
            team_name = get_ticket_details(ticket_key)
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    if successful_tickets:
        print("Successfully created tickets:")
        for ticket_key, team_id in successful_tickets:
            print(f"  {ticket_key} with team ID {team_id}")
        print("\nCheck these tickets in JIRA to see which team name appears.")
        print("The one showing 'Ops Engineering' is the correct team ID to use.")
    else:
        print("No tickets were created successfully. All team IDs failed validation.")