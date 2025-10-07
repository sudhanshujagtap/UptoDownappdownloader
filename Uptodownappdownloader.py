import os
import sys
import subprocess
import time
import zipfile
import argparse
import shutil
import logging
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/140.0.0.0 Safari/537.36"
}
TEMP_DIR = ".temp_apks"
MANIFEST_DIR = ".manifests"
APKTOOL_FILENAME = "apktool.jar"
APKTOOL_URL = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.12.1.jar"

DEV_URL_SLUGS = {
    "microsoft": "microsoft-corporation",
    "google": "google-llc",
    "facebook": "meta-platforms-inc",
    "techyonic": "techyonic"
}

def check_install_library(lib_name):
    try:
        __import__(lib_name)
    except ImportError:
        print(f"[!] Library '{lib_name}' not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib_name])
        print(f"[✓] Library '{lib_name}' installed.")

def ensure_apktool(script_dir):
    apktool_path = Path(script_dir) / APKTOOL_FILENAME
    if not apktool_path.exists():
        print("[!] Apktool not found. Downloading...")
        import requests
        r = requests.get(APKTOOL_URL, stream=True)
        with open(apktool_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[✓] Apktool downloaded -> {apktool_path}")
    return apktool_path

def safe_request(url, log, retries=5, backoff=2, **kwargs):
    import requests
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            log.warning(f"[!] Request failed ({attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                sleep_time = backoff ** attempt
                log.info(f"[+] Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                log.error(f"[-] Giving up on {url}")
                return None
            
def download_app(app_url, outdir, log):
    from bs4 import BeautifulSoup
    from tqdm import tqdm

    download_page = app_url + "/download"
    log.info(f"[+] Fetching download page: {download_page}")
    resp = safe_request(download_page, log)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    time.sleep(1)

    button = soup.select_one("button#detail-download-button[data-url]")
    if not button:
        log.warning(f"[-] No download button found for {app_url}")
        return None
    data_url = button['data-url']

    pkg_row = soup.find("th", string="Package Name")
    if not pkg_row:
        log.warning(f"[-] Could not find package name for {app_url}")
        return None
    pkg_name = pkg_row.find_next_sibling("td").text.strip()

    filepath = os.path.join(outdir, f"{pkg_name}.apk")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        log.info(f"[=] Already downloaded, skipping: {filepath}")
        return filepath

    final_url = f"https://dw.uptodown.net/dwn/{data_url}/uptodown-{pkg_name}.apk"
    r = safe_request(final_url, log, stream=True)
    if not r:
        return None

    total = int(r.headers.get('content-length', 0))
    with open(filepath, "wb") as f, tqdm(total=total, unit='B', unit_scale=True, desc=pkg_name) as bar:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))
    log.info(f"[✓] Saved: {filepath}")
    return filepath

def download_app_version(app_url, version_id, outdir, log):
    from bs4 import BeautifulSoup
    from tqdm import tqdm

    download_page = f"{app_url}/download/{version_id}"
    log.info(f"[+] Fetching older APK version: {download_page}")
    resp = safe_request(download_page, log)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    time.sleep(1)

    button = soup.select_one("button#detail-download-button[data-url]")
    if not button:
        log.warning(f"[-] No download button found for version {version_id}")
        return None
    data_url = button['data-url']

    pkg_row = soup.find("th", string="Package Name")
    if not pkg_row:
        log.warning(f"[-] Could not find package name for version {version_id}")
        return None
    pkg_name = pkg_row.find_next_sibling("td").text.strip()

    filepath = os.path.join(outdir, f"{pkg_name}_v{version_id}.apk")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        log.info(f"[=] Already downloaded, skipping: {filepath}")
        return filepath

    final_url = f"https://dw.uptodown.net/dwn/{data_url}/uptodown-{pkg_name}.apk"
    r = safe_request(final_url, log, stream=True)
    if not r:
        return None

    total = int(r.headers.get('content-length', 0))
    with open(filepath, "wb") as f, tqdm(total=total, unit='B', unit_scale=True, desc=f"{pkg_name}_v{version_id}") as bar:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))
    log.info(f"[✓] Saved: {filepath}")
    return filepath

def fetch_developer_apps(dev_url, outdir, developer_name, log):
    from bs4 import BeautifulSoup
    downloaded_apks = []
    apk_info_list = []

    os.makedirs(outdir, exist_ok=True)
    page = 1
    seen_apps = set()

    while True:
        url = f"{dev_url}?page={page}"
        log.info(f"[+] Fetching developer page: {url}")
        resp = safe_request(url, log)
        if not resp:
            break
        soup = BeautifulSoup(resp.text, "html.parser")

        app_items = soup.select("div.item")
        if not app_items:
            log.info("[+] No more apps found. Finished fetching apps.")
            break

        new_app_found = False
        for item in app_items:
            a_tag = item.select_one("div.name a[href*='/android']")
            if not a_tag:
                continue

            href = a_tag['href']
            app_url = href if href.startswith("http") else "https://en.uptodown.com" + href
            if app_url in seen_apps:
                continue
            seen_apps.add(app_url)
            new_app_found = True

            # Check file type
            download_page = app_url + "/download"
            resp_dl = safe_request(download_page, log)
            if not resp_dl:
                continue
            soup_dl = BeautifulSoup(resp_dl.text, "html.parser")
            file_type_row = soup_dl.find("th", string="File type")
            file_type = file_type_row.find_next_sibling("td").text.strip().lower() if file_type_row else "apk"

            apk_path = None
            if file_type != "apk":
                # check older versions
                versions_page = app_url + "/versions"
                resp_ver = safe_request(versions_page, log)
                if not resp_ver:
                    continue
                soup_ver = BeautifulSoup(resp_ver.text, "html.parser")
                apk_div = soup_ver.select_one("div[data-url][data-version-id] span.type[title='apk']")
                if apk_div:
                    parent_div = apk_div.find_parent("div", {"data-version-id": True})
                    version_id = parent_div["data-version-id"]
                    release_date = parent_div.select_one("span.date").text.strip()
                    log.info(f"[!] {a_tag.get('title', 'app')} latest version is XAPK. Using older APK from {release_date}")
                    apk_path = download_app_version(app_url, version_id, outdir, log)
                else:
                    log.warning(f"[-] {a_tag.get('title', 'app')} has no APK available. Skipping.")
            else:
                apk_path = download_app(app_url, outdir, log)

            if apk_path:
                downloaded_apks.append(apk_path)
                apk_info_list.append({
                    "app_name": a_tag.get('title', a_tag.text.strip()),
                    "pkg_name": Path(apk_path).stem,
                    "apk_path": apk_path,
                    "manifest_path": ""
                })

        if not new_app_found:
            log.info("[+] No new apps found on this page. Stopping pagination.")
            break

        page += 1
        time.sleep(1)

    return downloaded_apks, apk_info_list

def extract_manifests(apk_info_list, script_dir, log):
    apktool_path = Path(script_dir) / APKTOOL_FILENAME
    os.makedirs(MANIFEST_DIR, exist_ok=True)

    for info in apk_info_list:
        apk_path = info["apk_path"]
        decompiled_dir = Path(TEMP_DIR) / f"{Path(apk_path).stem}_decompiled"
        decompiled_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"[+] Decompiling {apk_path}")
        result = subprocess.run(
            ["java", "-jar", str(apktool_path), "d", "-f", apk_path, "-o", str(decompiled_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            log.warning(f"[-] Apktool failed for {apk_path}: {result.stderr}")
            continue

        manifest_src = decompiled_dir / "AndroidManifest.xml"
        if manifest_src.exists():
            manifest_dest = Path(MANIFEST_DIR) / f"{Path(apk_path).stem}_AndroidManifest.xml"
            shutil.copy(manifest_src, manifest_dest)
            log.info(f"[✓] Extracted AndroidManifest.xml -> {manifest_dest}")
            info["manifest_path"] = str(manifest_dest)
        else:
            log.warning(f"[-] AndroidManifest.xml not found in {apk_path}")

def create_excel_report(apk_info_list, outdir):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    bold_font = Font(bold=True)
    headers = ["App Name", "Package Name"]
    ws.append(headers)
    for col_num, _ in enumerate(headers, 1):
        ws.cell(row=1, column=col_num).font = bold_font

    for info in apk_info_list:
        app_name = info["app_name"].strip()
        if app_name.lower().startswith("download "):
            app_name = app_name[9:].strip()
        ws.append([app_name, info["pkg_name"]])

    excel_path = os.path.join(outdir, "apk_report.xlsx")
    wb.save(excel_path)
    return excel_path

def main():
    script_dir = os.path.abspath(os.path.dirname(__file__))

    for lib in ["requests", "bs4", "tqdm", "openpyxl"]:
        check_install_library(lib)

    parser = argparse.ArgumentParser(description="Uptodown App Downloader")
    parser.add_argument("--developer", help="Developer name or slug")
    parser.add_argument("--url", help="Direct app URL")
    parser.add_argument("--outdir", default=".", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    log_file_path = os.path.join(args.outdir, f"{args.developer or 'download'}_log.txt")
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
        handlers=[logging.FileHandler(log_file_path, encoding='utf-8'),
                  logging.StreamHandler(sys.stdout)]
    )
    log = logging.getLogger()

    ensure_apktool(script_dir)

    downloaded_apks = []
    apk_info_list = []

    dev_slug = DEV_URL_SLUGS.get(args.developer.lower(), args.developer) if args.developer else None

    try:
        if args.url:
            apk = download_app(args.url, args.outdir, log)
            if apk:
                downloaded_apks.append(apk)
                apk_info_list.append({
                    "app_name": Path(apk).stem,
                    "pkg_name": Path(apk).stem,
                    "apk_path": apk,
                    "manifest_path": ""
                })
        elif dev_slug:
            dev_url = f"https://en.uptodown.com/developer/{dev_slug}"
            downloaded_apks, apk_info_list = fetch_developer_apps(dev_url, args.outdir, args.developer, log)
        else:
            parser.print_help()
            return
    finally:
        if apk_info_list:
            extract_manifests(apk_info_list, script_dir, log)
            excel_path = create_excel_report(apk_info_list, args.outdir)
            log.info(f"[✓] Excel report created -> {excel_path}")

            zip_apk_log = os.path.join(args.outdir, f"{args.developer}_apks_and_log.zip")
            with zipfile.ZipFile(zip_apk_log, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for apk_file in downloaded_apks:
                    if os.path.exists(apk_file):
                        zipf.write(apk_file, arcname=os.path.basename(apk_file))
                if os.path.exists(log_file_path):
                    zipf.write(log_file_path, arcname=os.path.basename(log_file_path))
            log.info(f"[✓] APKs + log zipped -> {zip_apk_log}")

            zip_manifests = os.path.join(args.outdir, f"{args.developer}_manifests.zip")
            with zipfile.ZipFile(zip_manifests, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for manifest_file in Path(MANIFEST_DIR).glob("*"):
                    zipf.write(manifest_file, arcname=manifest_file.name)
            log.info(f"[✓] Manifests zipped -> {zip_manifests}")

        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        shutil.rmtree(MANIFEST_DIR, ignore_errors=True)
        log.info("[✓] Temporary folders cleaned up")
        log.info("[✓] Process complete.")

if __name__ == "__main__":
    main()
