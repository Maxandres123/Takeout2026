import os
import json
import shutil
import hashlib
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from datetime import datetime
from collections import defaultdict
import re
import threading
import queue
import sys

class TakeoutMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Takeout Unified Reconstruction Engine (Safe Copy)")
        self.root.geometry("900x700")
        
        # Threading & UI Safety
        self.is_running = False
        self.process_thread = None
        
        # Data structures
        self.source_folders = []
        self.destination_folder = None
        self.report_file = None
        self.ui_queue = queue.Queue() 

        # Timing
        self.start_time = None
        self.end_time = None
        
        # Statistics tracking (as a dictionary)
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
            "metadata_found_later": 0, 
            "drive_folders_processed": 0,
            "non_media_files_copied": 0, 
            "files_with_metadata": 0,
            # File Size Tracking (in bytes)
            "total_bytes_scanned": 0,
            "total_bytes_copied": 0,
            "duplicates_bytes_skipped": 0,
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
        
        tk.Label(main, text="Google Takeout Unified Reconstruction Engine", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.src_list = tk.Listbox(main, height=8)
        self.src_list.pack(fill=tk.X)
        
        btn_f = tk.Frame(main); btn_f.pack(pady=5)
        tk.Button(btn_f, text="Add Source Folder", command=self.add_src).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="Clear All", command=self.clear_src).pack(side=tk.LEFT, padx=5)
        
        self.dst_label = tk.Label(main, text="No Destination Set", fg="red")
        self.dst_label.pack(pady=5)
        
        tk.Button(main, text="Set Destination Folder", command=self.set_dst).pack(pady=5)
        
        # ExifTool Status Label
        self.exiftool_status = tk.Label(main, text="ExifTool: UNKNOWN", fg="orange")
        self.exiftool_status.pack(pady=2)
        
        self.warn_label = tk.Label(main, text="⚠️ SAFE MODE: Files will be COPIED (not moved)", fg="orange")
        self.warn_label.pack()
        
        self.start_btn = tk.Button(main, text="START UNIFIED MERGE", bg="#2ecc71", fg="white", 
                                   font=("Arial", 12, "bold"), command=self.start_process)
        self.start_btn.pack(pady=10, fill=tk.X)
        
        # Timer & Size Labels
        self.timer_label = tk.Label(main, text="", fg="blue")
        self.timer_label.pack(pady=5)
        self.size_label = tk.Label(main, text="", fg="purple", font=("Arial", 10))
        self.size_label.pack(pady=2)
        
        self.log_area = scrolledtext.ScrolledText(main, height=15, state='disabled', bg="#f8f9fa")
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Start UI Polling for Log Queue
        self.process_log_queue()

    def process_log_queue(self):
        """Process queued log messages on the main thread."""
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                self._update_log_display(msg)
        except queue.Empty:
            pass
        
        # Schedule next check (every 100ms to prevent CPU hogging)
        self.root.after(100, self.process_log_queue)

    def _log_safe(self, message):
        """Thread-safe logging method."""
        if isinstance(message, Exception):
            message = str(message)
        
        # Put in queue for main thread processing
        self.ui_queue.put(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")

    def _update_log_display(self, m):
        """Update the log widget (Must run on Main Thread)."""
        try:
            if not hasattr(self, 'log_area'): return
            
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, m)
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
            
            # Also write to report file if open
            if self.report_file:
                try:
                    with open(self.report_file, "a", encoding="utf-8") as f:
                        f.write(m.replace('\n', '')) 
                except: pass
        except Exception as e:
            print(f"Log UI Error: {e}")

    def format_bytes(self, bytes_val):
        """Format bytes into human readable string (KB, MB, GB)."""
        if bytes_val is None or bytes_val == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(bytes_val)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"

    def format_elapsed_time(self):
        """Format elapsed time in human readable format."""
        if not self.start_time or not self.end_time:
            return "0 seconds"
        
        elapsed = (self.end_time - self.start_time).total_seconds()
        
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{elapsed:.2f}s"

    def find_exiftool_executable(self):
        """Search for exiftool.exe in common locations and PATH."""
        possible_paths = [
            r"C:\Windows\System32\exiftool.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Scripts\exiftool.exe"),
            os.path.join(os.getcwd(), "exiftool.exe")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Check PATH using shutil.which (Cross-platform)
        import shutil
        exe = shutil.which("exiftool")
        if exe:
            self._log_safe(f"🔍 Found ExifTool at: {exe}")
            return exe
            
        return None

    def is_valid_version(self, version_string):
        """Check if output looks like a valid ExifTool version number."""
        if not version_string or not isinstance(version_string, str):
            return False
        pattern = r'^\d+\.\d+'
        return bool(re.match(pattern, version_string.strip()))

    def check_exiftool_on_startup(self):
        """Check if ExifTool is available using absolute paths."""
        exefile = self.find_exiftool_executable()
        
        if not exefile:
            self._log_safe("⚠️ ExifTool not found in PATH or common locations.")
            self.exiftool_status.config(text="⚠️ ExifTool NOT Configured", fg="red")
            return
        
        try:
            result = subprocess.run(
                [exefile, '-ver'], 
                capture_output=True, 
                text=True, 
                timeout=5,
                shell=False
            )
            
            version_output = result.stdout.strip()
            
            if result.returncode == 0 and self.is_valid_version(version_output):
                self.exiftool_available = True
                self._log_safe(f"✅ ExifTool detected at {exefile}: {version_output}")
                self.exiftool_path = exefile
                self.exiftool_status.config(text=f"✅ ExifTool Available ({version_output})", fg="green")
            else:
                raise Exception("Verification failed - invalid version output format")
        except Exception as e:
            self._log_safe(f"⚠️ ExifTool found but verification failed: {e}")
            self.exiftool_status.config(text="⚠️ ExifTool NOT Configured", fg="red")

    def detect_takeout_folders(self, parent_path):
        """Detect all subfolders named like 'takeout-xxxxx' within a parent."""
        takeout_dirs = []
        if not os.path.isdir(parent_path):
            return takeout_dirs
        
        try:
            for item in os.listdir(parent_path):
                full_path = os.path.join(parent_path, item)
                if os.path.isdir(full_path) and item.lower().startswith("takeout"):
                    # Quick check to see if it contains content
                    photos_found = False
                    files_found = False
                    for root, dirs, files in os.walk(full_path):
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.mp4']):
                                photos_found = True; break
                            if not f.lower().endswith(('.json', '.txt')):
                                files_found = True; break
                        if photos_found or files_found: break
                    
                    takeout_dirs.append(full_path)
        except Exception as e:
            self._log_safe(f"⚠️ Could not scan for Takeout folders in {parent_path}: {e}")
        
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
                    # Schedule UI update safely
                    self.root.after(0, lambda f=os.path.basename(folder): self.src_list.insert(tk.END, f))
                    added_count += 1
            
            if added_count == 0:
                if abs_p not in self.source_folders:
                    self.source_folders.append(abs_p)
                    self.root.after(0, lambda p=abs_p: self.src_list.insert(tk.END, os.path.basename(p)))
            
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
            # Schedule UI update safely
            self.root.after(0, lambda txt=f"Target: ...{self.destination_folder[-30:]}": self.dst_label.config(text=txt, fg="green"))

    def start_process(self):
        if not self.source_folders or not self.destination_folder:
            messagebox.showerror("Error", "Select sources and destination!")
            return
        
        # Final check for ExifTool before running heavy process
        if not self.exiftool_available:
            msg = (
                "⚠️ EXIFTOOL NOT CONFIGURED\n\n"
                "Metadata injection will be SKIPPED.\n\n"
                "To enable it:\n"
                "1. Download ExifTool from https://exiftool.org/\n"
                "2. Add folder to Windows PATH Environment Variable\n"
                "3. Restart this script.\n\n"
                "Continue without metadata?"
            )
            if not messagebox.askyesno("ExifTool Required", msg):
                return
        
        if not self.is_running:
            # Reset timing and counters
            self.start_time = datetime.now()
            self.end_time = None
            
            # Initialize file size tracking for this run
            self.stats["total_bytes_scanned"] = 0
            self.stats["total_bytes_copied"] = 0
            self.stats["duplicates_bytes_skipped"] = 0
            
            self.start_btn.config(state='disabled')
            self.is_running = True
            
            # Clear previous stats display
            self.root.after(0, lambda: self.size_label.config(text="Initializing..."))
            
            # Run in background thread to prevent UI freeze
            self.process_thread = threading.Thread(target=self.run_engine)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            messagebox.showinfo("Started", "Processing has begun. This may take a while.")
        else:
            messagebox.showwarning("Busy", "Process is already running!")

    def run_engine(self):
        seen_hashes = set()
        media_exts = ('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.webp')
        
        try:
            with open(self.report_file, "w", encoding="utf-8") as f:
                f.write(f"Migration started at {datetime.now()}\nSource Count: {len(self.source_folders)}\nMode: COPY (Safe)\nExifTool Available: {self.exiftool_available}\n\n")
        except Exception as e:
            self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Could not create report file: {err}"))
        
        # ===================== PHASE 1: FULL INDEXING =====================
        self.root.after(0, lambda: self._log_safe("🔍 Phase 1: Building complete master index..."))
        
        for src_root in self.source_folders:
            try:
                takeout_anchor = None
                # Find the best anchor folder inside the source
                if os.path.isdir(src_root):
                    for root, dirs, files in os.walk(src_root):
                        if "Takeout" in root or any(x in root.lower() for x in ["takeout", "photos"]):
                            takeout_anchor = root
                            break
                
                if not takeout_anchor:
                    takeout_anchor = src_root
                    
                for current_dir, dirs, files in os.walk(takeout_anchor):
                    # Skip trash folders
                    if any(x in current_dir.lower() for x in ["trash", "papelera"]): 
                        continue
                    
                    rel_path = os.path.relpath(current_dir, takeout_anchor)
                    
                    payload_files = [f for f in files if not f.lower().endswith(('.json', '.txt'))]
                    if not payload_files: 
                        continue
                    
                    album_name = os.path.basename(current_dir)
                    is_drive_folder = "drive" in current_dir.lower()
                    
                    for f_name in payload_files:
                        self.stats["scanned"] += 1
                        
                        # Track file size during scan (in main thread context via queue)
                        src_file = os.path.join(current_dir, f_name)
                        try:
                            file_size = os.path.getsize(src_file)
                            # Update stats safely using dictionary access
                            self.stats["total_bytes_scanned"] += file_size
                        except Exception as e:
                            pass
                        
                        is_media = f_name.lower().endswith(media_exts)
                        
                        file_info = {
                            "src_file": src_file,
                            "rel_path": rel_path,
                            "album_name": album_name,
                            "is_drive_folder": is_drive_folder,
                            "has_json": False,
                            "json_sources": [],
                            "timestamp_val": None 
                        }
                        
                        # Check for JSON companion
                        has_companion = False
                        for s in [".supplemental-metadata.json", ".json"]:
                            cand = src_file + s if not src_file.endswith(".json") else src_file.replace(".json", s)
                            if os.path.exists(cand):
                                file_info["has_json"] = True
                                has_companion = True
                                file_info["json_sources"].append({
                                    "path": cand,
                                    "src_root": os.path.basename(src_root),
                                    "rel_path": rel_path
                                })
                        
                        if is_media:
                            self.album_to_files[album_name].append(file_info)
                            
                        # Index Drive files too
                        if not is_media:
                            self.album_to_files[album_name].append(file_info)

                        if f_name not in self.master_file_index:
                            self.master_file_index[f_name] = {"files": [], "json_sources": []}
                        
                        self.master_file_index[f_name]["files"].append(file_info)
                        for js in file_info["json_sources"]:
                            self.master_file_index[f_name]["json_sources"].append(js)
            except Exception as e:
                self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Error scanning {src_root}: {err}"))

        # Report scan stats (after Phase 1 completes)
        scanned_size = self.format_bytes(self.stats["total_bytes_scanned"])
        self.root.after(0, lambda s=scanned_size: self.size_label.config(text=f"📊 Scanned: {s} ({self.stats['scanned']} files)"))
        
        self.stats["indexed_files"] = len(self.master_file_index)
        self.stats["total_albums_indexed"] = len(self.album_to_files)
        
        # ===================== PHASE 2: CROSS-ARCHIVE METADATA RESOLUTION =====================
        self.root.after(0, lambda: self._log_safe("🔍 Phase 2: Resolving metadata across archives..."))
        
        try:
            for f_name, data in self.master_file_index.items():
                files = data["files"]
                has_companion_anywhere = any(fi.get("has_json") for fi in files)
                
                if has_companion_anywhere:
                    for file_info in files:
                        if not file_info["has_json"]:
                            # Mark as having potential metadata (resolved later via JSON copy or update)
                            file_info["has_json"] = True 
                            self.stats["metadata_found_later"] += 1
            
            total_with_metadata = sum(1 for f_list in self.album_to_files.values() 
                                     for fi in f_list if fi.get("has_json"))
            self.stats["files_with_metadata"] = total_with_metadata
            
        except Exception as e:
            self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Error during metadata resolution: {err}"))
            
        # ===================== PHASE 3: COPY & INJECT =====================
        self.root.after(0, lambda: self._log_safe("🔍 Phase 3: Executing copy operations..."))
        
        try:
            for album_name, files in self.album_to_files.items():
                target_dir = os.path.join(self.destination_folder, album_name)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                    
                # Prepare batch updates
                metadata_updates = [] 
                
                for file_info in files:
                    src_file = file_info["src_file"]
                    f_name = os.path.basename(src_file)
                    
                    # 1. Duplicate Check (Hash) - Skip if already seen
                    try:
                        hasher = hashlib.sha256()
                        with open(src_file, 'rb') as f:
                            chunk = f.read(1048576) # First MB only for speed
                            if chunk: hasher.update(chunk)
                        h = hasher.hexdigest()
                        
                        if h in seen_hashes:
                            self.stats["duplicates"] += 1
                            
                            # Track bytes skipped for duplicates (estimate based on file size)
                            try:
                                dup_bytes = os.path.getsize(src_file)
                                self.stats["duplicates_bytes_skipped"] += dup_bytes
                            except Exception as e:
                                pass
                            
                            continue
                        seen_hashes.add(h)
                    except Exception as e:
                        self.stats["errors"] += 1
                        continue
                    
                    # All files now go to the main Album Directory for consistency.
                    final_target_dir = target_dir

                    # 2. Final Copy Execution
                    dest_p = os.path.join(final_target_dir, f_name)
                    
                    # Handle Filename Collisions
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
                        
                        # Track copied file size (direct dictionary access)
                        try:
                            copied_size = os.path.getsize(dest_p)
                            self.stats["total_bytes_copied"] += copied_size
                        except Exception as e:
                            pass
                        
                        # Copy JSON companion files for Drive folders too!
                        for js in file_info.get("json_sources", []):
                            if os.path.exists(js["path"]) and not os.path.exists(dest_p + ".json"):
                                shutil.copy2(js["path"], dest_p + ".json")
                                
                        self.stats["copied"] += 1
                        
                        # Prepare Metadata Update for Batch Processing
                        if file_info.get("has_json") and file_info["json_sources"]:
                            try:
                                json_path = file_info["json_sources"][0]["path"]
                                with open(json_path, 'r', encoding='utf-8') as jf:
                                    d = json.load(jf)
                                
                                ts = None
                                if 'photoTakenTime' in d and 'timestamp' in d['photoTakenTime']:
                                    ts = str(d['photoTakenTime']['timestamp']) # Keep as string to avoid int error
                                elif 'creationTime' in d and 'timestamp' in d['creationTime']:
                                    ts = str(d['creationTime']['timestamp'])
                                
                                geo = d.get('geoData', {}) or {}
                                lat, lon = geo.get('latitude'), geo.get('longitude')
                                
                                if ts:
                                    metadata_updates.append({
                                        "path": dest_p,
                                        "ts": ts,
                                        "lat": lat,
                                        "lon": lon
                                    })
                                else:
                                    self.stats["no_metadata"] += 1
                            except Exception as e:
                                self.root.after(0, lambda err=e: self._log_safe(f"⚠️ JSON parsing error for {dest_p}: {err}"))
                    except Exception as e:
                        self.root.after(0, lambda err=e: self._log_safe(f"⚠️ File copy error for {f_name}: {err}"))
                        self.stats["errors"] += 1
                        
                        if not src_file.lower().endswith(media_exts):
                            self.stats["non_media_files_copied"] += 1

            # Execute Metadata Updates in Batches (Group by timestamp to reduce ExifTool calls)
            if metadata_updates and self.exiftool_available:
                self.root.after(0, lambda: self._log_safe("🔍 Phase 3.5: Updating metadata..."))
                
                # Group updates by exact string value of timestamp
                batches = defaultdict(list)
                for item in metadata_updates:
                    batch_key = f"{item['ts']}_{item.get('lat', 0)}_{item.get('lon', 0)}"
                    batches[batch_key].append(item)

                for key, group in batches.items():
                    cmd = [self.exiftool_path, '-overwrite_original']
                    
                    # Parse timestamp safely
                    try:
                        ts_val = group[0]['ts']
                        dt_s = datetime.fromtimestamp(int(ts_val)).strftime('%Y:%m:%d %H:%M:%S') if isinstance(ts_val, (int, float)) else ts_val
                        
                        cmd.extend([f'-DateTimeOriginal={dt_s}', f'-CreateDate={dt_s}', f'-ModifyDate={dt_s}'])
                        
                        # Add GPS args if present in group
                        lat = group[0]['lat']
                        lon = group[0]['lon']
                        if lat is not None and abs(lat) > 0.01:
                            cmd.extend([f'-GPSLatitude={abs(lat)}', '-GPSLatitudeRef=N' if lat >= 0 else '-GPSLatitudeRef=S'])
                            cmd.extend([f'-GPSLongitude={abs(lon)}', '-GPSLongitudeRef=E' if lon >= 0 else '-GPSLongitudeRef=W'])
                    except Exception as e:
                        self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Batch ExifTool error: {err}"))
                        continue
                        
                    # Append files to command (Max 50 per batch to avoid Windows CMD length limits)
                    for item in group[:50]: 
                        cmd.append(item['path'])
                        
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=False)
                        if result.returncode == 0:
                            self.stats["updated_metadata"] += len(group)
                        else:
                            # Log partial failure
                            self.root.after(0, lambda err=result.stderr[:50]: self._log_safe(f"⚠️ Batch ExifTool failed: {err}"))
                            self.stats["metadata_update_failed"] += 1
                    except Exception as e:
                        self.stats["errors"] += 1
                        
            # ===================== PHASE B: ORPHAN RESOLUTION (O(N) FIX) =====================
            self.root.after(0, lambda: self._log_safe("🔍 Phase B: Re-linking orphaned JSONs..."))
            
            dest_files_map = {}
            try:
                for root, dirs, files in os.walk(self.destination_folder):
                    for f in files:
                        if not f.endswith('.json'):
                            base = os.path.splitext(f)[0]
                            # Store path relative to destination folder for easy move
                            dest_files_map[base] = os.path.join(root, f)
            except Exception as e:
                self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Error scanning destination: {err}"))

            try:
                for root, dirs, files in os.walk(self.destination_folder):
                    for j_file in files:
                        if j_file.endswith('.json'):
                            base_name = os.path.splitext(j_file)[0]
                            j_path = os.path.join(root, j_file)
                            
                            if base_name in dest_files_map:
                                media_partner = dest_files_map[base_name]
                                target_dir_for_json = os.path.dirname(media_partner)
                                
                                try:
                                    shutil.move(j_path, os.path.join(target_dir_for_json, j_file))
                                    self.stats["relinked"] += 1
                                    self.root.after(0, lambda p=j_file: self._log_safe(f"🔗 Re-linked {p}"))
                                except Exception as e:
                                    pass # Silently fail move attempts to avoid blocking
            except Exception as e:
                self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Error during re-linking: {err}"))

        except Exception as e:
            self.root.after(0, lambda err=e: self._log_safe(f"⚠️ Fatal Error during Phase 3: {err}"))
            
        # ===================== CALCULATE ELAPSED TIME & FINAL SIZE =====================
        self.end_time = datetime.now()
        elapsed_str = self.format_elapsed_time()
        
        copied_size = self.format_bytes(self.stats["total_bytes_copied"])
        scanned_size = self.format_bytes(self.stats["total_bytes_scanned"])
        dup_bytes_skipped = self.format_bytes(self.stats["duplicates_bytes_skipped"])
        
        # ===================== FINAL REPORT =====================
        report = (f"\n{'='*60}\n"
                  f"📊 FINAL REPORT\n"
                  f"{'='*60}\n"
                  f"⏱️  Total Time Elapsed:   {elapsed_str}\n"
                  f"🗄️  Storage Used:\n"
                  f"    Scanned:              {scanned_size} ({self.stats['scanned']} files)\n"
                  f"    Copied:               {copied_size} ({self.stats['copied']} files)\n"
                  f"    Duplicates Skipped:   {dup_bytes_skipped}\n"
                  f"\n🔍 Files Statistics:\n"
                  f"✅ Copied Files:          {self.stats['copied']}  <-- Original files preserved\n"
                  f"🔄 Duplicates:            {self.stats['duplicates']}\n"
                  f"📁 No Metadata (No JSON):{self.stats['no_metadata']}  <-- No Google Takeout JSON found\n"
                  f"📍 Metadata Found Later:  {self.stats['metadata_found_later']}\n"
                  f"📄 Files With Metadata:   {self.stats['files_with_metadata']}  <-- RESOLVED!\n"
                  f"🌎 Missing GPS:           {self.stats['missing_gps']}\n"
                  f"⚙️  Metadata Updated:      {self.stats['updated_metadata']}  <-- Photos only\n"
                  f"📁 Non-Media Copied:      {self.stats['non_media_files_copied']}  <-- Drive files!\n"
                  f"🗂️  Albums Indexed:        {self.stats['total_albums_indexed']}\n"
                  f"🔢 Files Indexed:         {self.stats['indexed_files']}\n"
                  f"❌ Errors:                {self.stats['errors']}")
        
        self.root.after(0, lambda r=report: self._log_safe(r))
        self.is_running = False
        self.start_btn.config(state='normal')
        
        # Update timer and size label with final stats (using dictionary access)
        total_used_str = f"⏱️  {elapsed_str} | 🗄️  Used: {copied_size}"
        self.timer_label.config(text=total_used_str, fg="green")
        self.size_label.config(text=f"📊 Scanned: {scanned_size} | Duplicates Skipped: {dup_bytes_skipped}", fg="purple")
        
        if not self.exiftool_available:
            messagebox.showwarning("Warning", "ExifTool was NOT available! Metadata injection was SKIPPED.")
            
        messagebox.showinfo("Done", f"Copy Complete in {elapsed_str}!\nTotal Storage Used: {copied_size}\nCheck log for metadata update status.\nNote: Drive files copied without metadata injection.")

    def _update_log_display(self, m):
        """Update the log widget (Must run on Main Thread)."""
        try:
            if not hasattr(self, 'log_area'): return
            
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, m)
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
            
            # Also write to report file if open
            if self.report_file:
                try:
                    with open(self.report_file, "a", encoding="utf-8") as f:
                        f.write(m.replace('\n', '')) 
                except: pass
        except Exception as e:
            print(f"Log UI Error: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TakeoutMaster(root)
    
    # Initial check on startup (non-blocking message only in logs/status label)
    app._log_safe("🔍 Checking prerequisites...")
    app.check_exiftool_on_startup()
    
    try:
        app.root.mainloop()
    except Exception as e:
        print(f"Mainloop Error: {e}")
