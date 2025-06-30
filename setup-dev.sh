#!/bin/bash
# Virtual environment setup script for AIxTerm

set -e

echo "Setting up AIxTerm development environment..."

# Check if Python 3.8+ is available
python_cmd=""
for cmd in python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$cmd" &> /dev/null; then
        version=$($cmd --version 2>&1 | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            python_cmd="$cmd"
            echo "Found Python $version at $(which $cmd)"
            break
        fi
    fi
done

if [ -z "$python_cmd" ]; then
    echo "Error: Python 3.8 or higher is required"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $python_cmd -m venv venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Install package in development mode
echo "Installing aixterm in development mode..."
pip install -e .

echo ""
echo "Development environment setup complete!"
echo ""
echo "To activate the environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  make test"
echo ""
echo "To check code quality:"
echo "  make quality-check"
echo ""
echo "To run aixterm:"
echo "  aixterm --help"
