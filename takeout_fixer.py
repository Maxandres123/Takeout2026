import os
import json
import shutil
import hashlib
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from datetime import datetime
from collections import defaultdict

class TakeoutMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Takeout Unified Reconstruction Engine (Safe Copy)")
        self.root.geometry("900x700")
        self.source_folders = []
        self.destination_folder = None
        self.report_file = None
        
        # Statistics tracking
        self.stats = {
            "scanned": 0,
            "copied": 0,
            "updated_metadata": 0,
            "duplicates": 0,
            "errors": 0,
            "collisions": 0,
            "no_metadata": 0,
            "relinked": 0,
            "missing_gps": 0,
            "metadata_update_failed": 0,
            "total_albums_indexed": 0,
            "indexed_files": 0,
            "metadata_found_later": 0
        }
        
        # Indexing structures
        self.master_file_index = {}
        self.album_to_files = defaultdict(list)
        
        # ExifTool Status
        self.exiftool_available = False
        self.exiftool_path = None

        self.setup_ui()
        self.check_exiftool_on_startup()

    def setup_ui(self):
        main = tk.Frame(self.root, padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="Google Takeout Professional Merger", font=("Arial", 16, "bold")).pack(pady=10)

        self.src_list = tk.Listbox(main, height=8)
        self.src_list.pack(fill=tk.X)

        btn_f = tk.Frame(main); btn_f.pack(pady=5)
        tk.Button(btn_f, text="Add Source Folder", command=self.add_src).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="Clear All", command=self.clear_src).pack(side=tk.LEFT, padx=5)

        self.dst_label = tk.Label(main, text="No Destination Set", fg="red")
        self.dst_label.pack(pady=5)
        
        tk.Button(main, text="Set Destination Folder", command=self.set_dst).pack(pady=5)

        # ExifTool Status Label (Updated dynamically)
        self.exiftool_status = tk.Label(main, text="ExifTool: UNKNOWN", fg="orange")
        self.exiftool_status.pack(pady=2)

        self.warn_label = tk.Label(main, text="⚠️ SAFE MODE: Files will be COPIED (not moved)", fg="orange")
        self.warn_label.pack()

        self.start_btn = tk.Button(main, text="START UNIFIED MERGE", bg="#2ecc71", fg="white", 
                                   font=("Arial", 12, "bold"), command=self.start_process)
        self.start_btn.pack(pady=10, fill=tk.X)

        self.log_area = scrolledtext.ScrolledText(main, height=15, state='disabled', bg="#f8f9fa")
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def find_exiftool_executable(self):
        """Search for exiftool.exe in common locations."""
        possible_paths = [
            r"C:\Windows\System32\exiftool.exe",
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'System32\\exiftool.exe'),
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Scripts\exiftool.exe"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If not found in specific paths, try searching PATH environment variable
        search_dirs = os.environ.get('PATH', '').split(';')
        for directory in search_dirs:
            exe_path = os.path.join(directory.strip(), 'exiftool.exe')
            if os.path.exists(exe_path):
                return exe_path
        
        return None

    def check_exiftool_on_startup(self):
        """Check if ExifTool is available using absolute paths."""
        exefile = self.find_exiftool_executable()
        
        if not exefile:
            self.log(f"⚠️ ExifTool not found in PATH or common locations.")
            self.exiftool_status.config(text="⚠️ ExifTool NOT Configured", fg="red")
            return
        
        try:
            # Use absolute path for verification to avoid PATH issues
            result = subprocess.run([exefile, '-ver'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and 'ExifTool' in result.stdout:
                self.exiftool_available = True
                version = result.stdout.strip().split('\n')[0]
                self.log(f"✅ ExifTool detected at {exefile}: {version}")
                self.exiftool_path = exefile
                self.exiftool_status.config(text=f"✅ ExifTool Available ({version})", fg="green")
            else:
                raise Exception("Verification failed")
        except Exception as e:
            self.log(f"⚠️ ExifTool found but verification failed: {e}")
            self.exiftool_status.config(text="⚠️ ExifTool NOT Configured", fg="red")

    def log(self, m):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {m}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        
        if self.report_file:
            try:
                with open(self.report_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}\n")
            except: pass
        
        self.root.update()

    def detect_takeout_folders(self, parent_path):
        """Detect all subfolders named like 'takeout-xxxxx' within a parent."""
        takeout_dirs = []
        if not os.path.isdir(parent_path):
            return takeout_dirs
        
        try:
            for item in os.listdir(parent_path):
                full_path = os.path.join(parent_path, item)
                if os.path.isdir(full_path) and item.lower().startswith("takeout"):
                    photos_found = False
                    for root, dirs, files in os.walk(full_path):
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.mp4']):
                                photos_found = True; break
                        if photos_found: break
                    if photos_found or item.lower().startswith("takeout"):
                        takeout_dirs.append(full_path)
        except Exception as e:
            self.log(f"⚠️ Could not scan for Takeout folders in {parent_path}: {e}")
        
        return sorted(takeout_dirs)

    def add_src(self):
        p = filedialog.askdirectory()
        if p:
            abs_p = os.path.abspath(p)
            potential_takeouts = self.detect_takeout_folders(abs_p)
            
            added_count = 0
            for folder in potential_takeouts:
                if folder not in self.source_folders:
                    self.source_folders.append(folder)
                    self.src_list.insert(tk.END, os.path.basename(folder))
                    added_count += 1
            
            if added_count == 0:
                if abs_p not in self.source_folders:
                    self.source_folders.append(abs_p)
                    self.src_list.insert(tk.END, os.path.basename(abs_p))
            
            if added_count > 1:
                messagebox.showinfo("Detected", f"Found {added_count} Takeout folders under '{os.path.basename(p)}'")

    def clear_src(self):
        self.source_folders = []
        self.src_list.delete(0, tk.END)

    def set_dst(self):
        p = filedialog.askdirectory()
        if p:
            self.destination_folder = os.path.abspath(p)
            self.report_file = os.path.join(self.destination_folder, "migration_audit_log.txt")
            self.dst_label.config(text=f"Target: ...{self.destination_folder[-30:]}", fg="green")

    def update_metadata_logic(self, media_path, timestamp, lat=None, lon=None):
        """Update EXIF metadata using ExifTool on the given file."""
        if not self.exiftool_available or not self.exiftool_path:
            return False
            
        cmd = [self.exiftool_path, '-overwrite_original']
        try:
            dt_s = datetime.fromtimestamp(int(timestamp)).strftime('%Y:%m:%d %H:%M:%S')
            cmd.append(f'-DateTimeOriginal={dt_s}')
            cmd.append(f'-CreateDate={dt_s}')
            cmd.append(f'-ModifyDate={dt_s}')
            cmd.append(f'-FileModifyDate={dt_s}')
            
            if lat is not None and lon is not None:
                if abs(lat) > 0.01 or abs(lon) > 0.01:
                    cmd.append(f'-GPSLatitude={abs(lat)}')
                    cmd.append(f'-GPSLongitude={abs(lon)}')
                    cmd.append('-GPSLatitudeRef=N' if lat >= 0 else '-GPSLatitudeRef=S')
                    cmd.append('-GPSLongitudeRef=E' if lon >= 0 else '-GPSLongitudeRef=W')
                else:
                    self.stats["missing_gps"] += 1
            
            cmd.append(media_path)
            
            # Run with shell=False for better control on Windows
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
            
            if result.returncode != 0:
                raise Exception(f"ExifTool failed with code {result.returncode}: {result.stderr}")
                
            return True
        except Exception as e:
            self.log(f"⚠️ Metadata update FAILED for {media_path}: {str(e)[:100]}")
            self.stats["metadata_update_failed"] += 1
            return False

    def start_process(self):
        if not self.source_folders or not self.destination_folder:
            message_err = "Select sources and destination!"
            messagebox.showerror("Error", message_err)
            return
        
        # Final check for ExifTool before running heavy process
        if not self.exiftool_available:
            msg = (
                "⚠️ EXIFTOOL NOT CONFIGURED\n\n"
                "Metadata injection will be SKIPPED.\n\n"
                "To enable it:\n"
                "1. Download ExifTool from https://exiftool.org/\n"
                "2. Extract to a folder (e.g., C:\\Tools)\n"
                "3. Add that folder path to your Windows System PATH Environment Variable\n"
                "4. Restart this script.\n\n"
                "Continue without metadata?"
            )
            if not messagebox.askyesno("ExifTool Required", msg):
                return

        if messagebox.askyesno("Confirm", "Start Copying all folders to unified library?"):
            self.start_btn.config(state='disabled')
            self.run_engine()

    def run_engine(self):
        seen_hashes = set()
        media_exts = ('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.webp', '.heic')
        
        try:
            with open(self.report_file, "w", encoding="utf-8") as f:
                f.write(f"Migration started at {datetime.now()}\nSource Count: {len(self.source_folders)}\nMode: COPY (Safe)\nExifTool Available: {self.exiftool_available}\n\n")
        except Exception as e:
            self.log(f"⚠️ Could not create report file: {e}")
        
        # ===================== PHASE 1: FULL INDEXING =====================
        self.log("🔍 Phase 1: Building complete master index of all files...")
        
        for src_root in self.source_folders:
            try:
                self.log(f"📂 Scanning Source Root: {os.path.basename(src_root)}")

                takeout_anchor = None
                for root, dirs, files in os.walk(src_root):
                    if "Takeout" in root or any(x in root.lower() for x in ["takeout", "photos"]):
                        takeout_anchor = root
                        break
                
                if not takeout_anchor:
                    takeout_anchor = src_root

                for current_dir, dirs, files in os.walk(takeout_anchor):
                    if any(x in current_dir.lower() for x in ["trash", "papelera"]): 
                        continue
                    
                    rel_path = os.path.relpath(current_dir, takeout_anchor)
                    
                    media_files = [f for f in files if f.lower().endswith(media_exts)]
                    payload_files = [f for f in files if not f.lower().endswith(('.json', '.txt'))]

                    if not payload_files: 
                        continue
                    
                    album_name = os.path.basename(current_dir)
                    
                    for f_name in payload_files:
                        self.stats["scanned"] += 1
                        src_file = os.path.join(current_dir, f_name)
                        is_media = f_name.lower().endswith(media_exts)
                        
                        file_info = {
                            "src_file": src_file,
                            "rel_path": rel_path,
                            "album_name": album_name,
                            "has_json": False,
                            "json_sources": []
                        }
                        
                        if is_media:
                            self.album_to_files[album_name].append(file_info)
                            
                            for s in [".supplemental-metadata.json", ".json"]:
                                cand = src_file + s if not src_file.endswith(".json") else src_file.replace(".json", s)
                                if os.path.exists(cand):
                                    file_info["has_json"] = True
                                    file_info["json_sources"].append({
                                        "path": cand,
                                        "src_root": os.path.basename(src_root),
                                        "rel_path": rel_path
                                    })
                        
                        if f_name not in self.master_file_index:
                            self.master_file_index[f_name] = {"files": [], "json_sources": []}
                        
                        self.master_file_index[f_name]["files"].append(file_info)
                        for js in file_info["json_sources"]:
                            self.master_file_index[f_name]["json_sources"].append(js)
            except Exception as e:
                self.log(f"⚠️ Error scanning {src_root}: {e}")

        self.stats["indexed_files"] = len(self.master_file_index)
        self.stats["total_albums_indexed"] = len(self.album_to_files)
        
        # ===================== PHASE 2: CROSS-ARCHIVE METADATA RESOLUTION =====================
        self.log("🔍 Phase 2: Resolving metadata across ALL archives...")
        
        try:
            for f_name, data in self.master_file_index.items():
                files = data["files"]
                
                has_companion_anywhere = False
                
                for file_info in files:
                    if file_info.get("has_json"):
                        has_companion_anywhere = True
                        break
                
                if has_companion_anywhere:
                    for file_info in files:
                        if not file_info["has_json"]:
                            file_info["has_json"] = True
                            self.stats["metadata_found_later"] += 1
        except Exception as e:
            self.log(f"⚠️ Error during metadata resolution: {e}")

        # ===================== PHASE 3: COPY & INJECT (Based on Resolved Index) =====================
        self.log("🔍 Phase 3: Executing copy operations based on resolved index...")
        
        try:
            for album_name, files in self.album_to_files.items():
                target_dir = os.path.join(self.destination_folder, album_name)

                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)

                for file_info in files:
                    src_file = file_info["src_file"]
                    f_name = os.path.basename(src_file)
                    
                    # 1. Duplicate Check (Hash)
                    try:
                        hasher = hashlib.sha256()
                        with open(src_file, 'rb') as f:
                            chunk = f.read(1048576)
                            if chunk: hasher.update(chunk)
                        h = hasher.hexdigest()

                        if h in seen_hashes:
                            self.stats["duplicates"] += 1
                            continue
                        seen_hashes.add(h)
                    except Exception as e:
                        self.stats["errors"] += 1
                        continue
                    
                    # Determine final destination
                    if not file_info.get("has_json"):
                        self.stats["no_metadata"] += 1
                        final_target_dir = os.path.join(self.destination_folder, "No_Metadata_Found", album_name)
                        
                        try:
                            if not os.path.exists(final_target_dir):
                                os.makedirs(final_target_dir, exist_ok=True)
                        except Exception as e:
                            self.log(f"⚠️ Could not create No_Metadata folder: {e}")
                    else:
                        final_target_dir = target_dir

                    # 2. Final Copy Execution
                    dest_p = os.path.join(final_target_dir, f_name)

                    if os.path.exists(dest_p):
                        name, ext = os.path.splitext(f_name)
                        count = 1
                        while True:
                            new_n = f"{name}_{count}{ext}"
                            dest_p = os.path.join(final_target_dir, new_n)
                            if not os.path.exists(dest_p): break
                            count += 1
                        self.stats["collisions"] += 1

                    try:
                        shutil.copy2(src_file, dest_p)
                        
                        for js in file_info.get("json_sources", []):
                            if os.path.exists(js["path"]) and not os.path.exists(dest_p + ".json"):
                                shutil.copy2(js["path"], dest_p + ".json")
                            
                        self.stats["copied"] += 1
                        
                        # Metadata Update on DESTINATION copy (Only if ExifTool is available)
                        if file_info.get("has_json") and file_info["json_sources"] and self.exiftool_available:
                            try:
                                json_path = file_info["json_sources"][0]["path"]
                                
                                with open(json_path, 'r', encoding='utf-8') as jf:
                                    d = json.load(jf)
                                
                                ts = None
                                if 'photoTakenTime' in d and 'timestamp' in d['photoTakenTime']:
                                    ts = d['photoTakenTime']['timestamp']
                                elif 'creationTime' in d and 'timestamp' in d['creationTime']:
                                    ts = d['creationTime']['timestamp']
                                
                                geo = d.get('geoData', {}) or {}
                                lat, lon = geo.get('latitude'), geo.get('longitude')
                                
                                if lat == 0.0 and lon == 0.0:
                                    self.stats["missing_gps"] += 1
                                
                                if ts and self.update_metadata_logic(dest_p, ts, lat, lon):
                                    self.log(f"✅ Metadata updated for {f_name}")
                                    self.stats["updated_metadata"] += 1
                            except Exception as e:
                                self.log(f"⚠️ JSON parsing or update error for {dest_p}: {str(e)[:100]}")
                                self.stats["errors"] += 1

                    except Exception as e:
                        self.log(f"⚠️ File copy error for {f_name}: {e}")
                        self.stats["errors"] += 1
        except Exception as e:
            self.log(f"⚠️ Error during Phase 3: {e}")

        # ===================== PHASE B: ORPHAN RESOLUTION (DESTINATION CLEANUP) =====================
        try:
            self.log("🔍 Starting Phase B: Re-linking orphaned JSONs in Destination...")

            if os.path.exists(self.destination_folder):
                for root, dirs, files in os.walk(self.destination_folder):
                    json_files = [f for f in files if f.endswith(".json")]

                    for j_file in json_files:
                        j_path = os.path.join(root, j_file)
                        base_name = j_file.replace(".json", "")
                        found_partner = False

                        for root2, dirs2, files2 in os.walk(self.destination_folder):
                            if found_partner: break

                            for f2 in files2:
                                if f2.startswith(base_name) and f2 != j_file:
                                    media_partner = os.path.join(root2, f2)
                                    target_dir_for_json = os.path.dirname(media_partner)

                                    try:
                                        shutil.move(j_path, os.path.join(target_dir_for_json, j_file))
                                        self.stats["relinked"] += 1
                                        self.log(f"🔗 Re-linked JSON to partner: {f2}")
                                        found_partner = True
                                    except Exception as e:
                                        pass
                                if found_partner: break
        except Exception as e:
            self.log(f"⚠️ Error during Phase B (JSON re-linking): {e}")

        # ===================== FINAL REPORT =====================
        report = (f"\n--- FINAL REPORT ---\n"
                  f"Scanned:         {self.stats['scanned']}\n"
                  f"Copied:          {self.stats['copied']}  <-- Original files preserved\n"
                  f"Duplicates:      {self.stats['duplicates']}\n"
                  f"No Metadata:     {self.stats['no_metadata']}\n"
                  f"Metadata Found Later (from other archives): {self.stats['metadata_found_later']}\n"
                  f"Missing GPS:     {self.stats['missing_gps']}\n"
                  f"Metadata Update Failed: {self.stats['metadata_update_failed']}  <-- Check this!\n"
                  f"Albums Indexed:  {self.stats['total_albums_indexed']}\n"
                  f"Files Indexed:   {self.stats['indexed_files']}\n"
                  f"Errors:          {self.stats['errors']}")

        self.log(report)
        self.start_btn.config(state='normal')
        
        if not self.exiftool_available:
            messagebox.showwarning("Warning", "ExifTool was NOT available! Metadata injection was SKIPPED.\n\nTo enable metadata:\n1. Download ExifTool from https://exiftool.org/\n2. Extract it to a folder (e.g., C:\\Tools)\n3. Add that folder to Windows PATH Environment Variables\n4. Restart this script.")
        
        messagebox.showinfo("Done", "Copy Complete! Check log for metadata update status.")


if __name__ == "__main__":
    root = tk.Tk()
    app = TakeoutMaster(root)
    
    # Initial check on startup (non-blocking message only in logs/status label)
    app.log("🔍 Checking prerequisites...")
    app.check_exiftool_on_startup()
    
    app.root.mainloop()
