# TAO RUN NOTES

## Quick Start
Just run:
```bat
run.bat
```

## Manual Setup Steps (if run.bat doesn't work)

### 1. Create Virtual Environment
```powershell
# Create new virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate
```

### 2. Install Dependencies
```powershell
# Install required packages
pip install -r requirements.txt
```

### 3. Run the Program
```powershell
# Start the application
python run.py
```

### 4. Deactivate When Done
```powershell
# When finished, deactivate the virtual environment
deactivate
```

## Troubleshooting

### If Virtual Environment Fails
```powershell
# Remove old venv
rm -r venv

# Create new one
python -m venv venv
```

### If Dependencies Installation Fails
```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Then install requirements
pip install -r requirements.txt
```

### If Program Won't Start
```powershell
# Check Python version (should be 3.8 or higher)
python --version

# Verify PyQt6 installation
pip show PyQt6
```

## Notes
- Make sure you have Python 3.8 or higher installed
- The program requires internet connection for API access
- API keys must be configured in the application settings
- Default model is set to "o1" with "high" reasoning effort 