# Google Takeout Unified Reconstruction Engine


[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20|%20macOS%20|%20Linux-blue.svg)]()


## Overview

The **Google Takeout Unified Reconstruction Engine** is a robust Python tool designed to consolidate fragmented Google Takeout exports into a single, organized media library. It intelligently handles multi-archive structures, enriches metadata using ExifTool, and operates in a safe "Copy Mode" by default to ensure your original data remains untouched during processing.

### What's New
- ✅ **Google Drive Support:** Now processes ALL files including PDFs, DOCX, and other documents from Google Drive backups
- ✅ **Cross-Archive Metadata Resolution:** Files with metadata in any archive are properly linked across all archives
- ✅ **Smart No-Metadata Handling:** Only truly orphaned files go to `No_Metadata_Found` folder
- ✅ **Enhanced Logging:** Detailed statistics tracking for better auditability


## Key Features

*   ** Safe Copy Mode:** By default, files are copied rather than moved. Your original Takeout archives remain intact for verification.
*   ** Auto-Detection:** Automatically identifies multiple `takeout-*` folders within a parent directory without manual configuration.
*   ** Metadata Enrichment:** Injects precise Date/Time and GPS coordinates into media headers using ExifTool.
*   ** GPS Validation:** Ignores zero-value coordinates (`0.0`) to avoid corrupting files with missing location data.
*   ** Orphan Resolution:** Automatically re-links JSON metadata files that were separated from their media partners during migration.
*   ** Google Drive Support:** Processes ALL file types including PDFs, DOCX, and other documents from Drive backups.
*   ** Audit Logging:** Generates a detailed `migration_audit_log.txt` for every operation performed.


## Prerequisites

### Python 3.8+
Ensure Python is installed and added to your PATH on all platforms.

```bash
python --version  # Should show 3.8 or higher
```

### ExifTool (Optional but Recommended)
Required for metadata injection into media files.

| Platform | Installation Instructions |
|----------|---------------------------|
| **Windows** | Download from [exiftool.org](https://exiftool.org/), extract, and add the folder containing `exiftool.exe` to your system PATH variable. Verify with: `exiftool -ver` in PowerShell. |
| **macOS** | Using Homebrew: `brew install exiftool`. Or download from [exiftool.org](https://exiftool.org/) and add to PATH. |
| **Linux** | Using package manager: `sudo apt install libimage-exiftool-perl` (Debian/Ubuntu) or `sudo yum install Image-ExifTool` (RHEL/CentOS). Verify with: `exiftool -ver`. |

> ⚠️ **Note:** The tool will run without ExifTool, but metadata injection will be skipped. A warning message will appear before processing begins.


## Installation & Usage

### 1. Clone or Download
Download the repository and extract it to your desired location (e.g., `C:\Projects\takeout_fixer` on Windows, `~/projects/takeout_fixer` on macOS/Linux).

```bash
git clone https://github.com/yourusername/takeout-reconstruction-engine.git
cd takeout-reconstruction-engine
```

### 2. Configure PowerShell Policy (Windows Only)
To ensure the script executes correctly and can invoke external tools via subprocess on Windows, you must set your PowerShell execution policy before running this tool.

**Run in an Administrator PowerShell session:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

> ℹ️ Note: This change applies only to the current terminal session and does not alter system-wide security settings.


### 3. Run the Application

#### Windows
```powershell
cd C:\Projects\takeout_fixer
python takeout_fixer.py
```

#### macOS / Linux
```bash
cd ~/projects/takeout_fixer
python3 takeout_fixer.py
```

> ⚠️ **Note:** On some systems, you may need to use `python` instead of `python3`.


### 4. GUI Workflow

1.  **Add Source Folder:** Select your parent folder containing multiple `takeout-*` archives (e.g., `E:\Testgooglefotos1`). The tool will auto-detect subfolders including Google Drive folders.
2.  **Set Destination Folder:** Choose where the unified library will be created.
3.  **START UNIFIED MERGE:** Click to begin processing.


## Expected Output Structure

```
Destination/
├── Album_Name_1/
│   ├── photo_001.jpg (with metadata)
│   └── photo_002.pdf
├── Google Drive/
│   ├── Document.pdf
│   └── Screenshot.png
└── No_Metadata_Found/       # Only files WITHOUT any JSON companions
    └── Album_Name_2/
        └── orphan_file.jpg
```


## Statistics & Reporting

The tool generates detailed statistics during processing:

| Statistic | Description |
|-----------|-------------|
| **Scanned** | Total files scanned across all archives |
| **Copied** | Files successfully copied to destination |
| **Duplicates** | Duplicate files skipped (SHA-256 hash check) |
| **No Metadata** | Files without JSON companions |
| **Metadata Found Later** | Cross-archive metadata resolution success count |
| **Files With Metadata** | Total files with resolved metadata after Phase 2 |
| **Missing GPS** | Files with zero-value coordinates (not injected) |
| **Metadata Updated** | Photos successfully updated with ExifTool |
| **Non-Media Copied** | Drive documents and other non-media files copied |


## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"exiftool not found"** | Ensure ExifTool is installed and added to your system PATH. Verify by typing `exiftool -ver` in terminal. On macOS/Linux, use Homebrew or package manager as shown above. |
| **PowerShell Warning (Windows)** | Run the `Set-ExecutionPolicy` command as Administrator before launching Python. |
| **No Metadata Found** | Check if `.json` or `.supplemental-metadata.json` files exist alongside your media. The tool creates a `No_Metadata_Found` folder for these items after cross-archive resolution completes. |
| **Duplicate Errors** | The tool uses SHA-256 hashing to prevent duplicates, but ensure you aren't selecting the same source path twice. |
| **ExifTool Verification Failed** | Ensure ExifTool is in your PATH and executable. On Windows, verify with `exiftool -ver` returns version number like "13.55". |
| **Permission Denied (Linux/macOS)** | Run terminal as user with write permissions to destination folder. Use `chmod +x takeout_fixer.py` if needed. |


## Advanced Configuration

### Customizing ExifTool Path (if not in PATH)
If you cannot add ExifTool to your system PATH, the tool will attempt to find it in common locations:
- Windows: `C:\Windows\System32\`, `%WINDIR%\System32\`
- macOS/Linux: Standard system paths

### Force Metadata Injection (Use with Caution)
To skip the ExifTool warning and force metadata injection, ensure ExifTool is properly installed before starting. The tool will automatically detect it.


## License
This project is licensed under the MIT License - see the LICENSE file for details.


## Contributing
Contributions are welcome! Please feel free to submit a Pull Request or open an Issue for bugs and feature requests.

### How to Contribute
1.  Fork the repository
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request


## Disclaimer

> ⚠️ **Always back up your data before running bulk file operations, even with safety features enabled.** While this tool operates in Copy Mode by default and includes multiple safeguards, no software can guarantee zero risk during file processing. Use at your own discretion.


**Author:** Maxezk  
**Version:** 2.0 (Drive Support Added)  
**Last Updated:** 2026 