import os
import shutil
from datetime import datetime

def backup_database():
    """Create a backup of the database files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = 'db_backups'
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    db_files = ['users.db', 'audit.db']
    backups = {}
    
    for db_file in db_files:
        if os.path.exists(db_file):
            backup_path = os.path.join(backup_dir, f'{db_file}.{timestamp}')
            shutil.copy2(db_file, backup_path)
            backups[db_file] = backup_path
    
    return backups

def restore_database(backups):
    """Restore database files from backups"""
    for original, backup in backups.items():
        if os.path.exists(backup):
            shutil.copy2(backup, original)
