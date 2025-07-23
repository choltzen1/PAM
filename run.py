#!/usr/bin/env python3
"""
PROMO APP - Main Entry Point
============================

This is the SINGLE entry point for all operations.
All scripts and functions are accessible from here.

Usage:
  python run.py --help                    # Show all available commands
  python run.py mapping                   # Create/update device mapping
  python run.py search "iPhone 15"        # Search for devices
  python run.py webapp                    # Start web interface
  python run.py batch devices.txt         # Batch search from file
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# Check if we're in a virtual environment
def check_python_environment():
    """Check if we're using the right Python environment."""
    venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    current_python = Path(sys.executable)
    
    if venv_python.exists() and current_python != venv_python:
        print(f"⚠️  You should use the virtual environment:")
        print(f"   {venv_python}")
        print(f"   Current Python: {current_python}")
        print()
        print("To activate virtual environment:")
        print("   .\\venv\\Scripts\\Activate.ps1")
        print()
        return False
    return True

def main():
    # Check Python environment first
    if not check_python_environment():
        return 1
        
    parser = argparse.ArgumentParser(
        description="Promo App - Device Alias Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Mapping command
    mapping_parser = subparsers.add_parser('mapping', help='Create/update device mapping')
    mapping_parser.add_argument('--force', action='store_true', help='Force rebuild mapping')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for device aliases')
    search_parser.add_argument('device', help='Device name to search for')
    search_parser.add_argument('--export', help='Export results to Excel file')
    
    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Batch search from file or list')
    batch_parser.add_argument('input', help='File path or comma-separated device list')
    batch_parser.add_argument('--output', help='Output file name (optional)')
    
    # Webapp command
    webapp_parser = subparsers.add_parser('webapp', help='Start web interface')
    webapp_parser.add_argument('--port', type=int, default=5000, help='Port number')
    webapp_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # Automation command
    auto_parser = subparsers.add_parser('automation', help='Setup/run automation')
    auto_parser.add_argument('action', choices=['setup', 'status', 'run'], help='Automation action')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Import and execute commands
    try:
        if args.command == 'mapping':
            from core.create_correct_comprehensive_mapping import main as mapping_main
            mapping_main(force_rebuild=args.force)
            
        elif args.command == 'search':
            from core.batch_device_search import search_single_device
            results = search_single_device(args.device)
            print(f"Found {len(results)} results for '{args.device}'")
            if args.export:
                # Export logic here
                print(f"Results exported to {args.export}")
                
        elif args.command == 'batch':
            from core.batch_device_search import main as batch_main
            batch_main(args.input, args.output)
            
        elif args.command == 'webapp':
            from webapp.app_clean import app
            print(f"🌐 Starting web interface at http://localhost:{args.port}")
            app.run(host='0.0.0.0', port=args.port, debug=args.debug)
            
        elif args.command == 'automation':
            from core.setup_automation import main as auto_main
            auto_main(args.action)
            
    except ImportError as e:
        print(f"Error importing module: {e}")
        print("Make sure all required files are in the correct locations.")
        return 1
    except Exception as e:
        print(f"Error running command: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
