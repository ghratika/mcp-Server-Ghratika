from auth.google_auth import get_credentials, get_gmail_service, get_drive_service
import sys

print("Checking token...")
try:
    creds = get_credentials()
    print(f"  Valid:   {creds.valid}")
    print(f"  Expiry:  {creds.expiry}")
except Exception as e:
    print(f"ERROR loading credentials: {e}")
    sys.exit(1)

print("\nTesting Gmail API...")
try:
    svc = get_gmail_service()
    profile = svc.users().getProfile(userId="me").execute()
    print(f"  Account:       {profile['emailAddress']}")
    print(f"  Total threads: {profile['threadsTotal']}")
except Exception as e:
    print(f"ERROR connecting to Gmail: {e}")
    sys.exit(1)

print("\nTesting Google Drive API...")
try:
    drive = get_drive_service()
    about = drive.about().get(fields="user").execute()
    print(f"  User: {about['user']['displayName']} ({about['user']['emailAddress']})")
except Exception as e:
    print(f"ERROR connecting to Drive: {e}")
    sys.exit(1)

print("\n All APIs connected successfully!")
