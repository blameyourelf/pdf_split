#!/usr/bin/env python
"""
Test runner script to execute all tests.
"""

import unittest
import os
import sys

def run_all_tests():
    """Run all tests and return True if all pass, False otherwise."""
    # Create a test loader
    loader = unittest.TestLoader()
    
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add test modules
    test_modules = [
        'test_database',
        'test_ward_manager',
        'test_pdf_processor'
    ]
    
    # Load tests from each module
    for module in test_modules:
        try:
            # Check if the module exists
            if os.path.exists(f"{module}.py"):
                tests = loader.loadTestsFromName(module)
                suite.addTests(tests)
            else:
                print(f"⚠️ Test module {module}.py not found, skipping...")
        except Exception as e:
            print(f"⚠️ Error loading tests from {module}: {e}")
    
    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run the tests
    print("=" * 70)
    print("Running tests...")
    print("=" * 70)
    result = runner.run(suite)
    
    # Summary
    print("=" * 70)
    print("Test Summary:")
    print(f"Run: {result.testsRun}")
    print(f"Errors: {len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 70)
    
    # Return True if all tests passed
    return len(result.errors) == 0 and len(result.failures) == 0

if __name__ == '__main__':
    success = run_all_tests()
    # Exit with appropriate status code
    sys.exit(0 if success else 1)
