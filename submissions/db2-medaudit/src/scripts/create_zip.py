import os
import zipfile

def create_project_zip():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    public_dir = os.path.join(base_dir, "public")
    os.makedirs(public_dir, exist_ok=True)
    
    zip_path = os.path.join(public_dir, "db2-medaudit-solution.zip")
    
    # Exclude directories and patterns
    exclude_dirs = {"node_modules", "dist", ".git", ".aistudio", "__pycache__", ".cache"}
    exclude_exts = {".zip", ".pyc", ".log"}
    
    print(f"Creating zip file at {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_exts or file.startswith('.'):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                
                # Exclude the zip file itself if located in base_dir
                if "db2-medaudit-solution.zip" in rel_path:
                    continue
                
                zipf.write(full_path, arcname=rel_path)
                print(f"  Added: {rel_path}")

    size_kb = os.path.getsize(zip_path) / 1024
    print(f"Zip created successfully! Size: {size_kb:.1f} KB")

if __name__ == "__main__":
    create_project_zip()
