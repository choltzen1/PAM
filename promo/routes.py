from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import os
from data.storage import PromoDataManager

# Create blueprint for promotion routes
promo_bp = Blueprint('promo', __name__)

# Initialize data manager
data_manager = PromoDataManager()

@promo_bp.route('/edit_promo/<promo_code>', methods=['GET', 'POST'])
def edit_promo(promo_code):
    """Handle editing of promotion data"""
    if request.method == 'POST':
        # Get the active tab
        active_tab = request.form.get('active_tab', 'Details')
        
        # Get current promo data
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            flash(f"Promotion {promo_code} not found", "error")
            return redirect(url_for('index'))
        
        # Handle SQL generation
        if request.form.get('generate_sql'):
            from promo.builders import generate_promo_eligibility_sql
            from datetime import datetime
            import time
            try:
                # Start timing SQL generation
                start_time = time.time()
                
                # Generate SQL using the dictionary data
                sql_content = generate_promo_eligibility_sql(promo_data)
                
                # End timing
                end_time = time.time()
                generation_time = end_time - start_time
                
                # Save SQL to promo with timestamp and performance data
                # Store full SQL - remove truncation to allow complete output
                promo_data['generated_sql'] = sql_content
                promo_data['sql_truncated'] = False
                    
                promo_data['sql_generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                promo_data['sql_generation_time'] = f"{generation_time:.4f}"
                promo_data['sql_length'] = len(sql_content)
                data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
                
                # Flash message with performance info
                flash(f"SQL generated successfully in {generation_time:.2f} seconds ({len(sql_content):,} characters)", "success")
                
                # Log performance warning if slow
                if generation_time > 5.0:
                    print(f"⚠️  WARNING: SQL generation for {promo_code} took {generation_time:.2f} seconds!")
                elif generation_time > 2.0:
                    print(f"⚠️  NOTICE: SQL generation for {promo_code} took {generation_time:.2f} seconds")
                    
            except Exception as e:
                flash(f"Error generating SQL: {str(e)}", "error")
        
        # Handle file uploads
        for file_key in ['sku_excel', 'tradein_excel']:
            if file_key in request.files:
                file = request.files[file_key]
                if file and file.filename:
                    try:
                        file_metadata = data_manager.save_excel_file(promo_code, file, file_key)
                        if file_metadata:
                            # Update the promo data with file metadata
                            if 'uploaded_files' not in promo_data:
                                promo_data['uploaded_files'] = {}
                            promo_data['uploaded_files'][file_key] = file_metadata
                            
                            # Process trade-in Excel file to populate trade tier data
                            if file_key == 'tradein_excel':
                                from promo.parsers import parse_tradein_excel
                                try:
                                    sql_statements = parse_tradein_excel(file_metadata['file_path'], promo_data)
                                    
                                    # Parse the SQL statements to extract tier information and populate form fields
                                    tier_data = {}
                                    for sql in sql_statements:
                                        # Extract tier and model information from SQL
                                        if 'TIER' in sql:
                                            # Find tier number in the SQL statement
                                            import re
                                            tier_match = re.search(r'TIER (\d+)', sql)
                                            make_match = re.search(r",'([^']+)','([^']+)',", sql)
                                            grp_id_match = re.search(r"Values \('([^']+)'", sql)
                                            
                                            if tier_match and make_match and grp_id_match:
                                                tier_num = tier_match.group(1)
                                                make = make_match.group(1)
                                                model = make_match.group(2)
                                                grp_id = grp_id_match.group(1)
                                                
                                                if tier_num not in tier_data:
                                                    tier_data[tier_num] = {
                                                        'make_model': grp_id,
                                                        'devices': []
                                                    }
                                                tier_data[tier_num]['devices'].append(f"{make} - {model}")
                                    
                                    # Update promo data with tier information
                                    for tier_num, data in tier_data.items():
                                        promo_data[f'trade_tier_{tier_num}_make_model'] = data['make_model']
                                        # You can also set default amounts, conditions, etc. based on your business logic
                                        if not promo_data.get(f'trade_tier_{tier_num}_cond_id'):
                                            promo_data[f'trade_tier_{tier_num}_cond_id'] = 'ST1'  # Default condition
                                    
                                    # Store the generated SQL statements for later use
                                    promo_data['tradein_sql_statements'] = sql_statements  
                                    
                                    flash(f"Trade-in Excel processed successfully. {len(sql_statements)} SQL statements generated.", "success")
                                    
                                except Exception as e:
                                    flash(f"Error processing trade-in Excel: {str(e)}", "warning")
                            
                            data_manager.save_promo(promo_code, promo_data)
                            flash(f"{file_key.replace('_', ' ').title()} uploaded successfully", "success")
                        else:
                            flash(f"Failed to save {file_key.replace('_', ' ')}", "error")
                    except Exception as e:
                        flash(f"Error uploading {file_key}: {str(e)}", "error")
        
        # Update promo fields based on active tab
        updated_fields = []
        for field_name, field_value in request.form.items():
            if field_name not in ['active_tab', 'generate_sql']:
                # Check if it's a new field or existing field
                if field_name in promo_data or field_value.strip():  # Update if field exists or has value
                    old_value = promo_data.get(field_name)
                    if old_value != field_value:
                        promo_data[field_name] = field_value
                        updated_fields.append(field_name)
        
        # Save changes
        if updated_fields:
            promo_data['last_changes'] = f"Updated {', '.join(updated_fields)} on {active_tab} tab"
            data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
            flash(f"Saved {active_tab} successfully", "success")
        
        # Redirect to maintain the active tab
        return redirect(url_for('promo.edit_promo', promo_code=promo_code, tab=active_tab))
    
    # GET request
    tab = request.args.get('tab', 'Details')
    promo_data = data_manager.get_promo(promo_code)
    if not promo_data:
        flash(f"Promotion {promo_code} not found", "error")
        return redirect(url_for('index'))
    
    return render_template('edit_promo.html', 
                         promo=promo_data, 
                         active_tab=tab,
                         soc_groupings=data_manager.get_soc_groupings(),
                         soc_grouping_details=data_manager.get_soc_grouping_details(),
                         account_types=data_manager.get_account_types(),
                         account_type_details=data_manager.get_account_type_details(),
                         sales_applications=data_manager.get_sales_applications(),
                         sales_application_details=data_manager.get_sales_application_details(),
                         user_name="Cade Holtzen")

@promo_bp.route('/clear_trade_data/<promo_code>', methods=['POST'])
def clear_trade_data(promo_code):
    """Clear all trade-related data for a promotion"""
    try:
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        # Clear trade-related fields
        trade_fields = [
            'trade_in_group_id', 'broken_trade',
            'trade_tier_1_make_model', 'trade_tier_1_amount', 'trade_tier_1_cond_id', 
            'trade_tier_1_min_fmv', 'trade_tier_1_max_fmv',
            'trade_tier_2_make_model', 'trade_tier_2_amount', 'trade_tier_2_cond_id',
            'trade_tier_2_min_fmv', 'trade_tier_2_max_fmv',
            'trade_tier_3_make_model', 'trade_tier_3_amount', 'trade_tier_3_cond_id',
            'trade_tier_3_min_fmv', 'trade_tier_3_max_fmv',
            'trade_tier_4_make_model', 'trade_tier_4_amount', 'trade_tier_4_cond_id',
            'trade_tier_4_min_fmv', 'trade_tier_4_max_fmv'
        ]
        
        for field in trade_fields:
            if field == 'broken_trade':
                promo_data[field] = 'N'  # Reset to default value
            else:
                promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
        return jsonify({'success': True, 'message': 'Trade data cleared successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/clear_tiers_data/<promo_code>', methods=['POST'])
def clear_tiers_data(promo_code):
    """Clear all tiers-related data for a promotion"""
    try:
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        # Clear tiers-related fields
        tier_fields = [
            'tiered_group_id',
            'tier_1_amount', 'tier_1_sku_group_id', 'tier_1_devices',
            'tier_2_amount', 'tier_2_sku_group_id', 'tier_2_devices',
            'tier_3_amount', 'tier_3_sku_group_id', 'tier_3_devices',
            'tier_4_amount', 'tier_4_sku_group_id', 'tier_4_devices'
        ]
        
        for field in tier_fields:
            promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
        return jsonify({'success': True, 'message': 'Tiers data cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/clear_segment_data/<promo_code>', methods=['POST'])
def clear_segment_data(promo_code):
    """Clear all segmentation-related data for a promotion"""
    try:
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        # Clear segmentation-related fields
        segment_fields = [
            'segment_name', 'sub_segment', 'segment_group_id', 'segment_level'
        ]
        
        for field in segment_fields:
            promo_data[field] = ''  # Clear the field
        
        # Save the updated promo data
        data_manager.save_promo(promo_code, promo_data, user_name="Cade Holtzen")
        
        return jsonify({'success': True, 'message': 'Segmentation data cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/delete_file/<promo_code>/<file_type>', methods=['POST'])
def delete_file(promo_code, file_type):
    """Delete an uploaded file for a promotion"""
    try:
        success = data_manager.delete_uploaded_file(promo_code, file_type)
        if success:
            return jsonify({'success': True, 'message': f'{file_type.replace("_", " ").title()} file deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete file'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@promo_bp.route('/download_file/<promo_code>/<file_type>')
def download_file(promo_code, file_type):
    """Download uploaded files for a promotion"""
    try:
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            flash("Promotion not found", "error")
            return redirect(url_for('index'))
        
        if not promo_data.get('uploaded_files') or file_type not in promo_data['uploaded_files']:
            flash("File not found", "error")
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        
        file_info = promo_data['uploaded_files'][file_type]
        file_path = file_info['path']
        
        if not os.path.exists(file_path):
            flash("File no longer exists", "error")
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        
        return send_file(file_path, as_attachment=True, download_name=file_info['original_name'])
    except Exception as e:
        flash(f"Error downloading file: {str(e)}", "error")
        return redirect(url_for('promo.edit_promo', promo_code=promo_code))

@promo_bp.route('/download_sql/<promo_code>')
def download_sql(promo_code):
    """Download generated SQL for a promotion"""
    try:
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            flash("Promotion not found", "error")
            return redirect(url_for('index'))
        
        if not promo_data.get('generated_sql'):
            flash("No SQL generated yet", "error")
            return redirect(url_for('promo.edit_promo', promo_code=promo_code))
        
        # Create temporary SQL file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(promo_data['generated_sql'])
            temp_path = f.name
        
        filename = f"{promo_code}_promo_eligibility_rules.sql"
        
        def remove_file(response):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            return response
        
        return send_file(temp_path, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f"Error downloading SQL: {str(e)}", "error")
        return redirect(url_for('promo.edit_promo', promo_code=promo_code))

@promo_bp.route('/get_full_sql/<promo_code>')
def get_full_sql(promo_code):
    """Get the full SQL for a promotion via AJAX"""
    try:
        promo_data = data_manager.get_promo(promo_code)
        if not promo_data:
            return jsonify({'success': False, 'error': 'Promotion not found'})
        
        sql = promo_data.get('generated_sql', '')
        if not sql:
            return jsonify({'success': False, 'error': 'No SQL found for this promotion'})
        
        return jsonify({
            'success': True, 
            'sql': sql,
            'length': len(sql)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})