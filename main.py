import os
import sys
import requests
import pandas as pd
import datetime

# --- CONFIG ---
EXCEL_FILE = "hook.xlsx"
HISTORY_FILE = "posted_history.txt"
VIDEO_FOLDER = "final_reels"

# Secrets (Loaded from GitHub Environment)
IG_USER_ID = os.environ.get("IG_USER_ID")
ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")

def get_next_reel():
    # 1. Load Excel
    df = pd.read_excel(EXCEL_FILE)
    
    # 2. Load History
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, 'w').close()
    
    with open(HISTORY_FILE, 'r') as f:
        posted_reels = [line.strip() for line in f.readlines()]

    # 3. Find first unposted reel
    for index, row in df.iterrows():
        reel_name = str(row['reel_name']).strip()
        if reel_name not in posted_reels:
            caption = row['Captions']
            video_path = os.path.join(VIDEO_FOLDER, reel_name)
            
            if os.path.exists(video_path):
                return reel_name, caption, video_path
    
    return None, None, None

def post_reel(video_path, caption):
    print(f"Uploading {video_path}...")
    
    # Step 1: Initialize Upload
    url = f"https://graph.facebook.com/v24.0/{IG_USER_ID}/media"
    
    # Since GitHub runs in the cloud, we can't use a local path directly in the API 
    # UNLESS we host it or use the Container Upload method.
    # HOWEVER: The simplest reliable way for GitHub Actions is to use the 
    # 'rupload' protocol (resumable upload) OR standard binary upload if supported.
    # BUT Instagram Graph API requires a PUBLIC URL for the video.
    
    # CRITICAL WORKAROUND for GITHUB ACTIONS:
    # We must construct the "Raw" GitHub URL for the video so Instagram can fetch it.
    # Format: https://raw.githubusercontent.com/<USER>/<REPO>/main/<PATH>
    
    repo_owner = os.environ.get("GITHUB_REPOSITORY_OWNER") # e.g., 'johndoe'
    repo_name = os.environ.get("GITHUB_REPOSITORY").split("/")[-1] # e.g., 'instagram-bot'
    branch = "main"
    
    # Construct Public URL
    relative_path = video_path.replace("\\", "/") # Ensure forward slashes
    public_video_url = f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/{branch}/{relative_path}"
    
    print(f"Public URL generated: {public_video_url}")
    
    payload = {
        'media_type': 'REELS',
        'video_url': public_video_url,
        'caption': caption,
        'access_token': ACCESS_TOKEN
    }
    
    # Create Container
    r = requests.post(url, data=payload)
    result = r.json()
    
    if 'id' not in result:
        print("Error creating container:", result)
        sys.exit(1)
        
    creation_id = result['id']
    print(f"Container ID: {creation_id}")
    
    # Step 2: Wait for Processing
    import time
    status_url = f"https://graph.facebook.com/v24.0/{creation_id}"
    while True:
        stat = requests.get(status_url, params={'fields': 'status_code', 'access_token': ACCESS_TOKEN}).json()
        code = stat.get('status_code')
        if code == 'FINISHED':
            break
        if code == 'ERROR':
            print("Error processing video")
            sys.exit(1)
        print("Processing... waiting 10s")
        time.sleep(10)
        
    # Step 3: Publish
    pub_url = f"https://graph.facebook.com/v24.0/{IG_USER_ID}/media_publish"
    pub = requests.post(pub_url, data={'creation_id': creation_id, 'access_token': ACCESS_TOKEN}).json()
    
    if 'id' in pub:
        print(f"Published successfully! ID: {pub['id']}")
        return True
    else:
        print("Publish failed:", pub)
        return False

def main():
    reel_name, caption, path = get_next_reel()
    
    if not reel_name:
        print("No new reels found in Excel (or all are posted).")
        sys.exit(0)
        
    print(f"Targeting: {reel_name}")
    
    success = post_reel(path, caption)
    
    if success:
        # Update History
        with open(HISTORY_FILE, 'a') as f:
            f.write(f"{reel_name}\n")
        print("History updated.")

if __name__ == "__main__":
    main()