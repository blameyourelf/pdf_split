"""
This script fixes duplicate route definitions in app.py and other common errors
"""
import re

def fix_duplicate_routes():
    # Path to the app.py file
    file_path = 'app.py'
    
    # Read the file content
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Find all patient route definitions
    pattern = r'(@app\.route\(\'\/patient\/\<patient_id\>\'\)\s*@login_required\s*def\s+patient\s*\(patient_id\))'
    matches = list(re.finditer(pattern, content))
    
    # If there are multiple definitions, keep the last one and comment out the others
    if len(matches) > 1:
        # Sort matches by position in reverse order to avoid offsetting issues
        matches.sort(key=lambda m: m.start(), reverse=True)
        
        # Keep the last route definition (which is actually the first one in our reversed list)
        kept_match = matches[0]
        
        # Comment out all other matches
        modified_content = content
        for i, match in enumerate(matches[1:]):
            start, end = match.span(0)
            # Add comment markers to each line
            lines = modified_content[start:end].split('\n')
            commented_lines = ['# ' + line for line in lines]
            modified_content = modified_content[:start] + '\n'.join(commented_lines) + modified_content[end:]
        
        # Write the modified content back to the file
        with open(file_path, 'w') as file:
            file.write(modified_content)
        
        print(f"Fixed {len(matches) - 1} duplicate patient route definitions")
    
    # Add missing imports
    if 'import click' not in content and '@click.command' in content:
        # Add the import statement after the last import
        import_pattern = r'^import .*$|^from .* import .*$'
        imports = list(re.finditer(import_pattern, content, re.MULTILINE))
        if imports:
            last_import = imports[-1]
            end_pos = last_import.end()
            modified_content = content[:end_pos] + "\nimport click\nfrom flask.cli import with_appcontext" + content[end_pos:]
            
            # Write the modified content back to the file
            with open(file_path, 'w') as file:
                file.write(modified_content)
            
            print("Added missing 'click' import")
    else:
        print("No missing imports found")

if __name__ == "__main__":
    fix_duplicate_routes()
