#!/usr/bin/env python3
"""
Script to update all references to old assets with new ones
Run this AFTER you've saved logo_new.png and payment_qr_new.png
"""
import os
import shutil

# Paths
OLD_LOGO = "static/images/logo2.png"
NEW_LOGO = "static/images/logo_new.png"
OLD_QR = "static/images/payment_qr.png"
NEW_QR = "static/images/payment_qr_new.png"

BACKUP_DIR = "backup_old_assets"

def main():
    print("Starting asset update process...\n")
    
    # Check if new assets exist
    if not os.path.exists(NEW_LOGO):
        print(f"ERROR: {NEW_LOGO} not found!")
        print("   Please save the new logo first as instructed.")
        return False
    
    if not os.path.exists(NEW_QR):
        print(f"ERROR: {NEW_QR} not found!")
        print("   Please save the new QR code first as instructed.")
        return False
    
    print("New assets found!")
    
    # Create backup directory
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")
    
    # Backup old assets
    if os.path.exists(OLD_LOGO):
        shutil.copy2(OLD_LOGO, os.path.join(BACKUP_DIR, "old_logo.png"))
        print(f"Backed up old logo")
    
    if os.path.exists(OLD_QR):
        shutil.copy2(OLD_QR, os.path.join(BACKUP_DIR, "old_qr.png"))
        print(f"Backed up old QR code")
    
    # Replace old assets with new ones
    shutil.copy2(NEW_LOGO, OLD_LOGO)
    print(f"Replaced logo: {OLD_LOGO}")
    
    shutil.copy2(NEW_QR, OLD_QR)
    print(f"Replaced QR code: {OLD_QR}")
    
    print("\nAsset update completed successfully!")
    print(f"Old assets backed up in: {BACKUP_DIR}/")
    print("\nYou can now restart your Flask app to see the changes!")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\nPlease follow the instructions above and try again.")
        exit(1)
