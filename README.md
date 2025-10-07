# UptoDownappdownloader

A Python-based utility for downloading APKs from Uptodown
, extracting their AndroidManifest.xml files, and generating a structured Excel report.
The script also packages the APKs, manifests, and logs into zip archives for easier sharing or analysis.

##✨ Features

Download APKs directly via app URL or by fetching all apps from a developer.

Automatically handles APK/XAPK by falling back to older APK versions if needed.

Extracts AndroidManifest.xml using apktool.

Generates a clean Excel report listing all apps and package names.

Bundles downloads and logs into zip archives.

Built-in retry logic for network requests.

##⚙️ Requirements

Python 3.8+

Java (for apktool)

The script automatically installs missing Python libraries on first run:

requests

beautifulsoup4

tqdm

openpyxl

##📦 Installation

Clone the repository:

git clone <your-private-repo-url>
cd uptodown-app-downloader


Ensure Python and Java are installed and available in your system PATH.

The script will download apktool.jar automatically if not found.

##🚀 Usage

Run the script with either a developer name/slug or a direct app URL.

Download all apps from a developer
python downloader.py --developer google --outdir ./downloads

Download a single app
python downloader.py --url "https://en.uptodown.com/android/download-app-name" --outdir ./downloads

##📂 Output

After running, you will get:

✅ Downloaded APK files in the specified output directory

✅ Extracted AndroidManifest.xml files (zipped)

✅ Excel report (apk_report.xlsx) listing app names & package names

✅ Logs of the entire operation

✅ Final ZIP archives:

<developer>_apks_and_log.zip

<developer>_manifests.zip

##📝 Examples
###Example 1: Download Google apps
python downloader.py --developer google --outdir ./google_apps

###Example 2: Download a single app
python downloader.py --url "https://en.uptodown.com/android/download-whatsapp" --outdir ./whatsapp_app

##⚠️ Notes

Some apps may only have XAPK available — in this case, the script attempts to fetch the latest APK version instead.

Requires an active internet connection for fetching APKs and apktool.

This tool is for research, analysis, and automation purposes. Please respect Uptodown’s terms of service when using it.

##📄 License

This repository is private. All rights reserved.
