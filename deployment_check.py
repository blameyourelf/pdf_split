#!/usr/bin/env python
"""
Deployment check script for Excel export functionality.
Run this during deployment to verify all dependencies are available.
"""

import sys
import importlib.util
import subprocess

def check_dependency(package_name):
    """Check if package is installed with detailed diagnostics."""
    print(f"\nChecking {package_name}...")
    print(f"Python executable: {sys.executable}")
    
    try:
        # Try importing the module
        module = importlib.import_module(package_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package_name} is installed (version: {version})")
        print(f"Module location: {module.__file__}")
        return True
    except ImportError as e:
        print(f"❌ Import Error: {str(e)}")
        
        # Check if it's installed via pip
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'list'], 
                                 capture_output=True, text=True)
            if package_name.lower() in result.stdout.lower():
                print(f"Note: {package_name} appears in pip list but cannot be imported!")
            print("Installed packages:")
            print(result.stdout)
        except Exception as e:
            print(f"Error checking pip: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_excel_export():
    """Test if Excel export functionality works properly."""
    print("\nTesting Excel Export...")
    
    try:
        import xlsxwriter
        import io
        print(f"XlsxWriter version: {xlsxwriter.__version__}")
        print(f"XlsxWriter location: {xlsxwriter.__file__}")
        
        # Try creating a simple Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Test')
        worksheet.write('A1', 'Test Excel Export')
        workbook.close()
        
        print("✅ Excel export test successful")
        return True
    except ImportError as e:
        print(f"❌ Import Error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Excel export test failed: {str(e)}")
        return False

def main():
    """Run deployment checks with enhanced diagnostics."""
    print("=== Running Enhanced Deployment Checks ===")
    
    # List of required packages
    required_packages = [
        'flask', 'flask_sqlalchemy', 'flask_login', 'PyPDF2',
        'werkzeug', 'sqlalchemy', 'reportlab', 'flask_wtf',
        'xlsxwriter'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        if not check_dependency(package):
            missing_packages.append(package)
    
    print("\n=== Environment Information ===")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path}")
    
    if missing_packages:
        print("\n❌ Missing dependencies:", ", ".join(missing_packages))
        print("Run: pip install " + " ".join(missing_packages))
    else:
        print("\n✅ All required packages are installed")
    
    # Test Excel functionality
    excel_working = test_excel_export()
    
    if not excel_working:
        print("\nTroubleshooting steps:")
        print("1. Try reinstalling xlsxwriter: pip uninstall xlsxwriter && pip install xlsxwriter")
        print("2. Check if xlsxwriter is installed in the correct Python environment")
        print("3. Try running: python -c 'import xlsxwriter; print(xlsxwriter.__file__)'")

if __name__ == "__main__":
    main()
