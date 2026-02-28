import os
import shutil
import zipfile
import re

# Config
BASE_DIR = "/Users/bytedance/agentkit/ai_movie_studio"
TARGET_DIR = os.path.join(BASE_DIR, "ai_movie_studio_submission_build")
ZIP_FILE = os.path.join(BASE_DIR, "ai_movie_studio_submission.zip")

IGNORE_PATTERNS = [
    ".venv", ".git", "__pycache__", ".DS_Store", 
    "ai_movie_studio_submission", "ai_movie_studio_submission_build",
    "ai_movie_studio_submission.zip", "clean_build", 
    ".idea", ".vscode", "submit_pr.sh", "agentkit-samples",
    "*.pyc", "*.log"
]

SENSITIVE_KEYS = [
    "VOLCENGINE_ACCESS_KEY", "VOLCENGINE_SECRET_KEY",
    "DATABASE_VIKING_API_KEY", "DATABASE_POSTGRESQL_PASSWORD",
    "PROMPT_MANAGEMENT_COZELOOP_TOKEN", "AGENTKIT_TOKEN"
]

def sanitize_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex replacement for sensitive keys
        for key in SENSITIVE_KEYS:
            # Matches `KEY: "value"` or `KEY=value`
            pattern = re.compile(rf'({key}\s*[:=]\s*)(["\'].*?["\']|[^#\n]+)', re.IGNORECASE)
            content = pattern.sub(r'\1""', content)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        # print(f"Sanitized: {file_path}")
    except Exception as e:
        print(f"Error sanitizing {file_path}: {e}")

def main():
    print("🚀 Preparing submission package...")
    
    # 1. Clean previous build
    if os.path.exists(TARGET_DIR):
        shutil.rmtree(TARGET_DIR)
        
    # 2. Copy files manually to handle ignore logic better
    def ignore_func(directory, files):
        return [f for f in files if any(p in f for p in IGNORE_PATTERNS)]

    print(f"Copying files to {TARGET_DIR}...")
    shutil.copytree(BASE_DIR, TARGET_DIR, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))
    
    # 3. Sanitize
    print("Sanitizing files...")
    for root, dirs, files in os.walk(TARGET_DIR):
        # Remove .env and config.yaml, keep examples
        if ".env" in files:
            os.remove(os.path.join(root, ".env"))
        if "config.yaml" in files:
            os.remove(os.path.join(root, "config.yaml"))
            
        for file in files:
            if file == "agentkit.yaml" or file.endswith(".yaml") or file.endswith(".env.example"):
                sanitize_file(os.path.join(root, file))

    # 4. Zip
    if os.path.exists(ZIP_FILE):
        os.remove(ZIP_FILE)
        
    print(f"Creating zip file: {ZIP_FILE}...")
    shutil.make_archive(ZIP_FILE.replace('.zip', ''), 'zip', TARGET_DIR)
                
    # 5. Cleanup
    shutil.rmtree(TARGET_DIR)
    print("✅ Done! Submission package ready.")

if __name__ == "__main__":
    main()
