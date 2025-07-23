from flask import Flask, render_template, request, jsonify, send_file
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.batch_device_search import batch_device_search, search_single_device, load_device_mapping, load_excel_data
from config import RESULTS_DIR, FLASK_HOST, FLASK_PORT, FLASK_DEBUG, MAPPING_FILE

app = Flask(__name__)
app.secret_key = 'promo-app-secret-key'

@app.route('/')
def dashboard():
    """Main dashboard"""
    try:
        # Get system stats
        mapping_df = load_device_mapping()
        excel_df = load_excel_data()
        
        stats = {
            'total_aliases': len(mapping_df) if mapping_df is not None else 0,
            'total_skus': len(excel_df) if excel_df is not None else 0,
            'searchable_devices': len(mapping_df['manufacturer_name'].unique()) if mapping_df is not None else 0
        }
        
        # Get recent results
        results_dir = PROJECT_ROOT / RESULTS_DIR
        recent_files = []
        
        if results_dir.exists():
            excel_files = list(results_dir.glob('*.xlsx'))
            excel_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for file in excel_files[:5]:
                recent_files.append({
                    'name': file.name,
                    'created': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'size_kb': round(file.stat().st_size / 1024, 1)
                })
        
        return render_template('dashboard_old.html', 
                             stats=stats, 
                             recent_files=recent_files,
                             state={'last_update': 'Just now', 'total_devices': stats.get('total_skus', 0), 'mapped_devices': stats.get('searchable_devices', 0)},
                             recent_results=recent_files)
    
    except Exception as e:
        return render_template('dashboard_old.html', stats={'error': str(e)}, recent_files=[])

@app.route('/search')
def search():
    """Single device search page"""
    return render_template('search_original.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint for single device search"""
    try:
        data = request.get_json()
        device_name = data.get('device', '').strip()
        
        if not device_name:
            return jsonify({'success': False, 'error': 'No device name provided'})
        
        results = search_single_device(device_name)
        
        if results is not None and not results.empty:
            return jsonify({
                'success': True,
                'count': len(results),
                'results': results.head(20).to_dict('records')  # Limit to first 20 for performance
            })
        else:
            return jsonify({'success': True, 'count': 0, 'results': []})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/batch')
def batch_page():
    """Batch search page"""
    return render_template('batch_search.html')

@app.route('/api/batch', methods=['POST'])
def api_batch():
    """API endpoint for batch device search"""
    try:
        data = request.get_json()
        devices_input = data.get('devices', [])
        
        # Handle both string and list inputs for backward compatibility
        if isinstance(devices_input, str):
            # Legacy: comma-separated string
            device_input = devices_input.strip()
            if not device_input:
                return jsonify({'success': False, 'error': 'No devices provided'})
            device_list = [d.strip() for d in device_input.split(',') if d.strip()]
        elif isinstance(devices_input, list):
            # New: array of device names
            device_list = [d.strip() for d in devices_input if d and d.strip()]
        else:
            return jsonify({'success': False, 'error': 'Invalid devices format'})
        
        if not device_list:
            return jsonify({'success': False, 'error': 'No valid devices found'})
        
        # Run batch search
        result = batch_device_search(device_list)
        
        if result and result['total_results'] > 0:
            # Create Excel file
            results_file = result['results_file']
            excel_file = Path(results_file).with_suffix('.xlsx')
            
            # Read CSV and create Excel
            results_df = pd.read_csv(results_file)
            summary_df = pd.read_csv(result['summary_file'])
            
            # Clean up for Excel export
            export_df = results_df.copy()
            if 'Search_Term' in export_df.columns:
                export_df = export_df.drop('Search_Term', axis=1)
            
            # Prepare preview results (first 10 matches)
            preview_results = []
            if len(results_df) > 0:
                preview_df = results_df.head(10)
                preview_results = preview_df.to_dict('records')
            
            # Create detailed summary by device
            device_summary = {}
            for device in device_list:
                device_matches = results_df[results_df.get('Search_Term', '') == device] if 'Search_Term' in results_df.columns else []
                device_summary[device] = len(device_matches)
            
            # Create Excel file
            with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, sheet_name='Device Results', index=False, startrow=4, header=False)
                summary_df.to_excel(writer, sheet_name='Search Summary', index=False)
                
                # Add headers and formatting
                workbook = writer.book
                worksheet = writer.sheets['Device Results']
                
                # Formats
                title_format = workbook.add_format({'bold': True, 'font_size': 14})
                header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
                merged_header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
                
                # Title and info
                worksheet.write('A1', 'Batch Device Search Results', title_format)
                worksheet.write('A2', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
                worksheet.write('A3', f'Total Results: {len(export_df)} | Search Terms: {", ".join(device_list)}')
                
                # Get column positions based on actual data columns
                columns = list(export_df.columns)
                print(f"DEBUG: Columns found: {columns}")  # Debug line
                
                # Row 5 (0-indexed as row 4) - Header row with merged cells
                # Merge cells A-B for "Material" and C-D for "Material Group" IN THE SAME ROW
                worksheet.merge_range(4, 0, 4, 1, 'Material', merged_header_format)  # A5:B5
                worksheet.merge_range(4, 2, 4, 3, 'Material Group', merged_header_format)  # C5:D5
                
                # Write remaining individual column headers in the same row
                for i, col in enumerate(columns):
                    if i >= 4:  # Only write headers for columns E and beyond
                        worksheet.write(4, i, col, header_format)
                
                # Auto-adjust column widths
                for i, col in enumerate(columns):
                    max_length = max(
                        len(col),
                        export_df[col].astype(str).str.len().max() if not export_df.empty else 0
                    )
                    worksheet.set_column(i, i, min(max_length + 2, 50))
            
            return jsonify({
                'success': True,
                'message': f'Found {result["total_results"]} devices',
                'excel_file': excel_file.name,
                'total_results': result['total_results'],
                'devices_searched': result['devices_searched'],
                'summary': device_summary,
                'preview_results': preview_results
            })
        
        else:
            # Create summary for devices with no results
            device_summary = {device: 0 for device in device_list}
            
            return jsonify({
                'success': True,
                'message': 'No devices found',
                'total_results': 0,
                'devices_searched': len(device_list),
                'summary': device_summary,
                'preview_results': []
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download/<filename>')
def download_file(filename):
    """Download results file"""
    try:
        file_path = PROJECT_ROOT / RESULTS_DIR / filename
        if file_path.exists():
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files')
def list_files():
    """List available result files"""
    try:
        results_dir = PROJECT_ROOT / RESULTS_DIR
        files = []
        
        if results_dir.exists():
            for file in results_dir.iterdir():
                if file.is_file():
                    files.append({
                        'name': file.name,
                        'size': file.stat().st_size,
                        'created': file.stat().st_mtime
                    })
        
        files.sort(key=lambda x: x['created'], reverse=True)
        return jsonify({'files': files})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
