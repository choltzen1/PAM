from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.batch_device_search import search_devices_batch
from core.device_mapping_updater import DeviceMappingUpdater
from core.create_correct_comprehensive_mapping import get_base_model
import pandas as pd
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

@app.route('/')
def dashboard():
    """Main dashboard showing system status"""
    try:
        # Get system status
        updater = DeviceMappingUpdater()
        state = updater.load_current_state()
        
        # Check for alerts
        alerts = []
        if os.path.exists('../temp/alerts'):
            alert_files = [f for f in os.listdir('../temp/alerts') if f.startswith('🚨')]
            alerts = alert_files
        
        # Check for unmapped devices
        unmapped_count = 0
        if os.path.exists('../data/unmapped_devices.csv'):
            try:
                unmapped_df = pd.read_csv('../data/unmapped_devices.csv')
                unmapped_count = len(unmapped_df)
            except:
                pass
        
        return render_template('dashboard.html', 
                             state=state, 
                             alerts=alerts,
                             unmapped_count=unmapped_count)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', 
                             state={}, 
                             alerts=[],
                             unmapped_count=0)

@app.route('/search', methods=['GET', 'POST'])
def device_search():
    """Device search interface"""
    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        
        if not search_query:
            flash('Please enter a device to search for', 'error')
            return render_template('search.html')
        
        try:
            # Use your existing batch search function
            results = search_devices_batch(search_query)
            
            return render_template('search_results.html', 
                                 query=search_query,
                                 results=results)
        except Exception as e:
            flash(f'Search error: {str(e)}', 'error')
            return render_template('search.html')
    
    return render_template('search.html')

@app.route('/unmapped')
def unmapped_devices():
    """View unmapped devices that need attention"""
    try:
        unmapped_devices = []
        if os.path.exists('../data/unmapped_devices.csv'):
            df = pd.read_csv('../data/unmapped_devices.csv')
            unmapped_devices = df.to_dict('records')
        
        return render_template('unmapped.html', devices=unmapped_devices)
    except Exception as e:
        flash(f'Error loading unmapped devices: {str(e)}', 'error')
        return render_template('unmapped.html', devices=[])

@app.route('/test_mapping', methods=['GET', 'POST'])
def test_mapping():
    """Test device mapping patterns"""
    if request.method == 'POST':
        device_name = request.form.get('device_name', '').strip()
        
        if not device_name:
            flash('Please enter a device name to test', 'error')
            return render_template('test_mapping.html')
        
        try:
            # Test the mapping
            base_model = get_base_model(device_name)
            
            # Check if it's mappable
            is_mappable = base_model != device_name
            
            result = {
                'device_name': device_name,
                'base_model': base_model,
                'is_mappable': is_mappable,
                'mapping_type': 'Automatic' if is_mappable else 'Manual attention needed'
            }
            
            return render_template('test_results.html', result=result)
        except Exception as e:
            flash(f'Test error: {str(e)}', 'error')
            return render_template('test_mapping.html')
    
    return render_template('test_mapping.html')

@app.route('/system_status')
def system_status():
    """System status and recent activity"""
    try:
        updater = DeviceMappingUpdater()
        state = updater.load_current_state()
        
        # Get recent reports
        reports = []
        if os.path.exists('../temp/reports'):
            report_files = [f for f in os.listdir('../temp/reports') if f.startswith('update_report_')]
            reports = sorted(report_files, reverse=True)[:5]  # Last 5 reports
        
        # Get Excel file info
        excel_info = updater.get_excel_file_info()
        
        return render_template('system_status.html', 
                             state=state,
                             reports=reports,
                             excel_info=excel_info)
    except Exception as e:
        flash(f'Error loading system status: {str(e)}', 'error')
        return render_template('system_status.html', 
                             state={},
                             reports=[],
                             excel_info=None)

@app.route('/api/run_check')
def api_run_check():
    """API endpoint to run manual check"""
    try:
        updater = DeviceMappingUpdater()
        result = updater.detect_new_devices()
        
        if result:
            new_devices, current_df = result
            return jsonify({
                'status': 'success',
                'new_devices_count': len(new_devices),
                'total_devices': len(current_df)
            })
        else:
            return jsonify({
                'status': 'success',
                'message': 'No new devices found'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/device_suggestions')
def api_device_suggestions():
    """API endpoint for device search suggestions"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 3:
        return jsonify([])
    
    try:
        # Load device mapping for suggestions
        df = pd.read_csv('../data/device_alias_mapping.csv')
        suggestions = df[df['Marketing_Alias'].str.contains(query, case=False, na=False)]['Marketing_Alias'].unique()[:10]
        return jsonify(suggestions.tolist())
    except:
        return jsonify([])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
