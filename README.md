# Google Takeout Unified Reconstruction Engine

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)](https://www.microsoft.com/windows)

##  Overview
The **Google Takeout Unified Reconstruction Engine** is a robust Python tool designed to consolidate fragmented Google Takeout exports into a single, organized media library. It intelligently handles multi-archive structures, enriches metadata using ExifTool, and operates in a safe "Copy Mode" by default to ensure your original data remains untouched during processing.

##  Key Features
*   ** Safe Copy Mode:** By default, files are copied rather than moved. Your original Takeout archives remain intact for verification.
*   ** Auto-Detection:** Automatically identifies multiple `takeout-*` folders within a parent directory without manual configuration.
*   ** Metadata Enrichment:** Injects precise Date/Time and GPS coordinates into media headers using ExifTool.
*   ** GPS Validation:** Ignores zero-value coordinates (`0.0`) to avoid corrupting files with missing location data.
*   ** Orphan Resolution:** Automatically re-links JSON metadata files that were separated from their media partners during migration.
*   ** Audit Logging:** Generates a detailed `migration_audit_log.txt` for every operation performed.

## Important: Windows PowerShell Execution Policy
To ensure the script executes correctly and can invoke external tools (like ExifTool) via subprocess on Windows, you must set your PowerShell execution policy before running this tool.

**Run the following command in an Administrator PowerShell session:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
Note: This change applies only to the current terminal session and does not alter system-wide security settings.

Prerequisites
Python 3.8+: Ensure Python is installed and added to your PATH.
ExifTool: Required for metadata injection.
Download from exiftool.org.
Install it or add the directory containing exiftool.exe to your system PATH variable.
Sufficient Disk Space: Since this tool operates in Copy Mode, ensure you have enough free space on your destination drive for a full duplicate of your media library.
Installation & Usage
1. Clone or Download
Download the repository and extract it to your desired location (e.g., C:\Projects\takeout_fixer).

2. Configure PowerShell Policy
Open PowerShell as Administrator and run:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
3. Run the Application
Navigate to the project directory in your terminal:

cd C:\Projects\takeout_fixer
python takeout_fixer.py
4. GUI Workflow
Add Source Folder: Select your parent folder containing multiple takeout-* archives (e.g., E:\Testgooglefotos1). The tool will auto-detect subfolders.
Set Destination Folder: Choose where the unified library will be created.
START UNIFIED MERGE: Click to begin processing.
Troubleshooting
Issue	Solution
"exiftool not found"	Ensure ExifTool is installed and added to your system PATH. Verify by typing exiftool in PowerShell.
PowerShell Warning	Run the Set-ExecutionPolicy command as Administrator before launching Python.
No Metadata Found	Check if .json or .supplemental-metadata.json files exist alongside your media. The tool creates a No_Metadata_Found folder for these items.
Duplicate Errors	The tool uses SHA-256 hashing to prevent duplicates, but ensure you aren't selecting the same source path twice.
License
This project is licensed under the MIT License - see the LICENSE file for details.

Contributing
Contributions are welcome! Please feel free to submit a Pull Request or open an Issue for bugs and feature requests.

Note: Always back up your data before running bulk file operations, even with safety features enabled.
Author:Maxezk
