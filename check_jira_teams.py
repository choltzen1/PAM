#!/usr/bin/env python3
"""
Quick script to check JIRA team names for given team IDs
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# JIRA configuration
JIRA_URL = os.environ.get('JIRA_URL', 'https://t-mobile-stage.atlassian.net')
JIRA_USERNAME = os.environ.get('JIRA_USERNAME', '')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN', '')

# Team IDs to check
team_ids = ['12756', '12762', '12748', '12793', '12778']

def get_team_info(team_id):
    """Get team information from JIRA API"""
    try:
        # Try to get team information using the team API
        url = f"{JIRA_URL}/rest/api/2/customfield/10279/context/10075/option/{team_id}"
        
        response = requests.get(
            url,
            auth=(JIRA_USERNAME, JIRA_API_TOKEN),
            headers={'Accept': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('value', f'Unknown team {team_id}')
        else:
            return f"Error {response.status_code}: {response.text[:100]}"
            
    except Exception as e:
        return f"Exception: {str(e)[:100]}"

if __name__ == "__main__":
    print("Checking JIRA Team IDs...")
    print(f"JIRA URL: {JIRA_URL}")
    print(f"Username: {JIRA_USERNAME}")
    print("-" * 50)
    
    for team_id in team_ids:
        team_name = get_team_info(team_id)
        print(f"Team ID {team_id}: {team_name}")