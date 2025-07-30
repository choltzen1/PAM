#!/usr/bin/env python3
"""
JIRA Field Explorer
Tool to discover custom fields and their IDs in your JIRA instance
"""

import requests
import urllib3
import json
from pprint import pprint

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def explore_jira_fields(email, api_token, base_url="https://t-mobile-stage.atlassian.net"):
    """
    Explore JIRA fields to find R2D2 Team ID or similar fields
    """
    print("🔍 JIRA Field Explorer")
    print("=" * 50)
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (email, api_token)
    
    # 1. Get all fields in the JIRA instance
    print("\n1️⃣ Getting all fields...")
    fields_url = f"{base_url}/rest/api/3/field"
    
    try:
        response = requests.get(fields_url, headers=headers, auth=auth, verify=False)
        if response.status_code == 200:
            fields = response.json()
            
            print(f"✅ Found {len(fields)} total fields")
            
            # Look for R2D2 related fields
            r2d2_fields = []
            team_fields = []
            custom_fields = []
            
            for field in fields:
                field_id = field.get('id', '')
                field_name = field.get('name', '').lower()
                field_type = field.get('schema', {}).get('type', '')
                
                # Store custom fields
                if field_id.startswith('customfield_'):
                    custom_fields.append(field)
                
                # Look for R2D2 related fields
                if 'r2d2' in field_name:
                    r2d2_fields.append(field)
                
                # Look for team related fields
                if 'team' in field_name:
                    team_fields.append(field)
            
            print(f"\n🤖 R2D2 Related Fields ({len(r2d2_fields)}):")
            if r2d2_fields:
                for field in r2d2_fields:
                    print(f"  • {field['id']}: {field['name']} ({field.get('schema', {}).get('type', 'unknown')})")
            else:
                print("  ❌ No R2D2 fields found")
            
            print(f"\n👥 Team Related Fields ({len(team_fields)}):")
            if team_fields:
                for field in team_fields:
                    print(f"  • {field['id']}: {field['name']} ({field.get('schema', {}).get('type', 'unknown')})")
            else:
                print("  ❌ No team fields found")
            
            print(f"\n🔧 All Custom Fields ({len(custom_fields)}):")
            for field in custom_fields:
                field_name = field.get('name', '')
                field_id = field.get('id', '')
                field_type = field.get('schema', {}).get('type', 'unknown')
                print(f"  • {field_id}: {field_name} ({field_type})")
            
            return custom_fields, r2d2_fields, team_fields
            
        else:
            print(f"❌ Error getting fields: {response.status_code} - {response.text}")
            return [], [], []
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return [], [], []

def explore_project_fields(email, api_token, project_key="CPO", base_url="https://t-mobile-stage.atlassian.net"):
    """
    Get fields available for a specific project
    """
    print(f"\n2️⃣ Getting fields for project {project_key}...")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (email, api_token)
    
    # Get create meta for the project to see available fields
    meta_url = f"{base_url}/rest/api/3/issue/createmeta"
    params = {
        "projectKeys": project_key,
        "expand": "projects.issuetypes.fields"
    }
    
    try:
        response = requests.get(meta_url, headers=headers, auth=auth, params=params, verify=False)
        if response.status_code == 200:
            meta_data = response.json()
            
            if meta_data.get('projects'):
                project = meta_data['projects'][0]
                print(f"✅ Project: {project.get('name', project_key)}")
                
                for issue_type in project.get('issuetypes', []):
                    print(f"\n📋 Issue Type: {issue_type.get('name', 'Unknown')}")
                    fields = issue_type.get('fields', {})
                    
                    # Look for custom fields in this issue type
                    custom_fields = {k: v for k, v in fields.items() if k.startswith('customfield_')}
                    
                    print(f"  Custom fields available: {len(custom_fields)}")
                    for field_id, field_info in custom_fields.items():
                        field_name = field_info.get('name', 'Unknown')
                        field_type = field_info.get('schema', {}).get('type', 'unknown')
                        required = field_info.get('required', False)
                        
                        # Highlight potentially relevant fields
                        highlight = ""
                        if any(keyword in field_name.lower() for keyword in ['r2d2', 'team', 'id']):
                            highlight = " ⭐"
                        
                        print(f"    • {field_id}: {field_name} ({field_type}){' [REQUIRED]' if required else ''}{highlight}")
                        
                        # Show allowed values if available
                        if 'allowedValues' in field_info:
                            values = field_info['allowedValues'][:5]  # Show first 5 values
                            value_names = [v.get('value', v.get('name', str(v))) for v in values]
                            print(f"      Values: {', '.join(value_names)}{'...' if len(field_info['allowedValues']) > 5 else ''}")
            
        else:
            print(f"❌ Error getting project meta: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def search_field_by_name(email, api_token, search_term="r2d2", base_url="https://t-mobile-stage.atlassian.net"):
    """
    Search for fields containing a specific term
    """
    print(f"\n3️⃣ Searching for fields containing '{search_term}'...")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (email, api_token)
    
    # Get all fields and filter
    fields_url = f"{base_url}/rest/api/3/field"
    
    try:
        response = requests.get(fields_url, headers=headers, auth=auth, verify=False)
        if response.status_code == 200:
            fields = response.json()
            
            matching_fields = []
            for field in fields:
                field_name = field.get('name', '').lower()
                field_id = field.get('id', '')
                
                if search_term.lower() in field_name or search_term.lower() in field_id.lower():
                    matching_fields.append(field)
            
            print(f"✅ Found {len(matching_fields)} fields matching '{search_term}':")
            for field in matching_fields:
                field_id = field.get('id', '')
                field_name = field.get('name', '')
                field_type = field.get('schema', {}).get('type', 'unknown')
                print(f"  • {field_id}: {field_name} ({field_type})")
            
            return matching_fields
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return []

def main():
    """
    Main function to run the JIRA field explorer
    """
    print("JIRA Field Explorer - Find R2D2 Team ID Field")
    print("=" * 60)
    
    # Get credentials
    email = input("Enter your JIRA email: ").strip()
    api_token = input("Enter your JIRA API token: ").strip()
    
    if not email or not api_token:
        print("❌ Email and API token are required")
        return
    
    # Explore fields
    custom_fields, r2d2_fields, team_fields = explore_jira_fields(email, api_token)
    
    # Explore project-specific fields
    explore_project_fields(email, api_token, "CPO")
    
    # Search for specific terms
    search_terms = ["r2d2", "team", "id"]
    for term in search_terms:
        search_field_by_name(email, api_token, term)
    
    print("\n" + "=" * 60)
    print("✅ Field exploration complete!")
    print("\n💡 Tips:")
    print("  • Look for customfield_* IDs that contain 'R2D2' or 'Team' in the name")
    print("  • Check if the field is available for the CPO project and Task issue type")
    print("  • Test with a small value first before using in production")
    print("  • The field might be named differently (e.g., 'R2-D2', 'Robot Team', etc.)")

if __name__ == "__main__":
    main()
