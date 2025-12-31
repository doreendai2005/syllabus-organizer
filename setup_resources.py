#!/usr/bin/env python3
"""
Setup script to create Google Drive folder and Doc for testing.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']


def authenticate():
    """Authenticate with Google."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return creds


def setup_resources():
    """Create Google Drive folder and Doc for syllabus automation."""
    print("Authenticating with Google...")
    creds = authenticate()
    drive_service = build('drive', 'v3', credentials=creds)

    # 1. Create Drive Folder
    folder_metadata = {
        'name': 'Syllabus Readings',
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')
    print(f"Created Folder: 'Syllabus Readings' (ID: {folder_id})")

    # 2. Create Google Doc in the folder
    doc_metadata = {
        'name': 'Syllabus Master List',
        'mimeType': 'application/vnd.google-apps.document',
        'parents': [folder_id]
    }
    doc = drive_service.files().create(body=doc_metadata, fields='id').execute()
    doc_id = doc.get('id')
    print(f"Created Doc: 'Syllabus Master List' (ID: {doc_id})")

    # 3. Save IDs to config file
    with open('config.txt', 'w') as f:
        f.write(f"FOLDER_ID={folder_id}\n")
        f.write(f"DOC_ID={doc_id}\n")

    print("\nSetup complete!")
    print(f"Config saved to config.txt")
    print(f"\nView your doc at:")
    print(f"https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == '__main__':
    setup_resources()
