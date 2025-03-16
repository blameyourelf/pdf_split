#!/usr/bin/env python
"""
Deployment check script for Excel export functionality.
Run this during deployment to verify all dependencies are available.
"""

import sys
import importlib.util

def check_dependency(package_name):
    """Check if package is installed."""
    package_spec = importlib.util.find_spec(package_name)
    if package_spec is None:
        return False
    return True

def test_excel_export():
    """Test if Excel export functionality works properly."""
    try:
        import xlsxwriter
        import io
        
        # Try creating a simple Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Test')
        worksheet.write('A1', 'Test Excel Export')
        workbook.close()
        
        print(f"✅ Excel export test successful - XlsxWriter {xlsxwriter.__version__} is working properly")
        return True
    except ImportError:
        print("❌ XlsxWriter is not installed")
        return False
    except Exception as e:
        print(f"❌ Excel export test failed: {str(e)}")
        return False

def main():
    """Run deployment checks."""
    print("Running deployment checks...")
    
    # Check required dependencies
    dependencies = [
        'flask', 
        'flask_sqlalchemy', 
        'flask_login', 
        'PyPDF2', 
        'werkzeug', 
        'sqlalchemy', 
        'reportlab', 
        'flask_wtf',
        'xlsxwriter'
    ]
    
    missing = []
    for dep in dependencies:
        if check_dependency(dep):
            print(f"✅ {dep} is installed")
        else:
            print(f"❌ {dep} is missing")
            missing.append(dep)
    
    # Test Excel export
    excel_working = test_excel_export()
    
    # Summary
    print("\n=== Deployment Check Summary ===")
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print("Run: pip install " + " ".join(missing))
    else:
        print("✅ All dependencies installed")
    
    if not excel_working:
        print("❌ Excel export is not working")
        print("Recommendation: Check XlsxWriter installation and compatibility")
    
    if missing or not excel_working:
        sys.exit(1)
    else:
        print("✅ All checks passed! Deployment should work correctly.")
        sys.exit(0)

if __name__ == "__main__":
    main()
