#!/bin/bash
# Azure App Service startup script for PAM
# This script installs ODBC Driver 18 and starts the Flask application

echo "=================================================="
echo "PAM Application Startup"
echo "=================================================="

# Log environment info
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"

# Install ODBC Driver 18 for SQL Server
echo ""
echo "📦 Installing ODBC Driver 18 for SQL Server..."

# Update package lists
apt-get update -qq

# Install dependencies
apt-get install -y -qq curl apt-transport-https gnupg

# Add Microsoft repository
curl -s https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl -s https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list

# Update and install ODBC driver
apt-get update -qq
ACCEPT_EULA=Y apt-get install -y -qq msodbcsql18 unixodbc-dev

echo "✅ ODBC Driver 18 installed"

# Verify ODBC installation
echo ""
echo "ODBC Drivers available:"
odbcinst -q -d

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "✅ Python dependencies installed"

# Start Gunicorn
echo ""
echo "🚀 Starting Gunicorn..."
echo "  Workers: 4"
echo "  Timeout: 600 seconds"
echo "  Bind: 0.0.0.0:8000"
echo ""

exec gunicorn \
  --bind=0.0.0.0:8000 \
  --timeout 600 \
  --workers 4 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  app:app
