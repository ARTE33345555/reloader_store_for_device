#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reloaded Nokia Client (PyS60 + console fallback)
Usage:
  - On PyS60 phone (if PyS60 installed): run with `--server-url http://yourserver:8000`
  - On PC/console: run the same, you'll get console UI.

This client only downloads .sis/.sisx/.jar files and shows SHA-256.
It does NOT bypass signatures or DRM. Use only with legal packages.
"""

from __future__ import print_function
import os, sys, json, hashlib, time, argparse, math

# Try to import PyS60 modules
try:
    import appuifw, e32, sys as s60sys
    py_s60 = True
except Exception:
    py_s60 = False

# For HTTP
try:
    # Python3
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except Exception:
    # Python2
    from urllib2 import urlopen, Request, URLError, HTTPError

CHUNK = 32768

def sha256_of_path(path, chunk_size=CHUNK):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def fetch_json(url, timeout=15):
    req = Request(url)
    req.add_header('User-Agent', 'Reloaded-Nokia-Client/1.0')
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    # bytes -> str for py3
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    return json.loads(data)

def download_with_progress(url, out_path, on_progress=None):
    req = Request(url)
    req.add_header('User-Agent', 'Reloaded-Nokia-Client/1.0')
    with urlopen(req, timeout=30) as resp:
        total = resp.getheader('Content-Length')
        total = int(total) if total and total.isdigit() else None
        downloaded = 0
        with open(out_path, 'wb') as out:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)
    return out_path

# UI helpers for PyS60
def pys60_menu(title, options):
    try:
        return appuifw.popup_menu(options, title)
    except Exception:
        # fallback
        return None

def pys60_input(prompt, default=""):
    try:
        return appuifw.query(prompt, "text", default)
    except Exception:
        return default

def pys60_note(text, kind="info"):
    try:
        appuifw.note(text, kind)
    except Exception:
        print(text)

# Determine download folder on device
def get_device_download_folder():
    # PyS60 typical paths
    if os.path.exists(u"e:\\"):
        base = u"e:\\Downloads"
    elif os.path.exists(u"c:\\"):
        base = u"c:\\Downloads"
    else:
        base = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.exists(base):
        try:
            os.makedirs(base)
        except Exception:
            pass
    return base

# Try launching installer on device
def try_launch_installer(path):
    # On Symbian PyS60, e32.start_exe may start executable, but may not always trigger SIS installer.
    try:
        if py_s60:
            e32.start_exe(path)
            return True
    except Exception:
        pass
    # On desktop: try default opener
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
            return True
        else:
            # attempt xdg-open / open
            import subprocess
            opener = "xdg-open" if os.name == "posix" else None
            if opener:
                subprocess.Popen([opener, path])
                return True
    except Exception:
        pass
    return False

# Main flows
def client_flow(server_url):
    server_url = server_url.rstrip("/")
    apps_url = server_url + "/apps"
    try:
        metas = fetch_json(apps_url)
    except Exception as e:
        if py_s60:
            pys60_note(u"Ошибка соединения: %s" % unicode_safe(e))
        else:
            print("Failed to fetch apps:", e)
        return

    if not metas:
        if py_s60:
            pys60_note(u"Список приложений пуст.")
        else:
            print("No apps available on server.")
        return

    # Build titles
    titles = []
    for a in metas:
        t = u"{title} ({ver})".format(title=a.get('title') or a.get('id'), ver=a.get('version', '?'))
        titles.append(t)

    if py_s60:
        idx = pys60_menu(u"Reloaded Nokia Store", titles)
        if idx is None:
            return
    else:
        # Console UI
        print("Available apps:")
        for i,a in enumerate(metas):
            print("[{i}] {title}  platform:{platform} ver:{ver} size:{size}".format(
                i=i, title=(a.get('title') or a.get('id')), platform=a.get('platform'), ver=a.get('version','?'), size=a.get('size', '?')))
        sel = input("Choose index to download (enter to quit): ").strip()
        if sel == "":
            return
        try:
            idx = int(sel)
        except:
            print("Invalid selection"); return

    app_meta = metas[idx]
    show_app_details_and_download(app_meta, server_url)

def unicode_safe(x):
    try:
        return unicode(x)
    except:
        try:
            return str(x)
        except:
            return repr(x)

def show_app_details_and_download(meta, server_url):
    # details
    title = meta.get('title') or meta.get('id')
    ver = meta.get('version', '?')
    size = meta.get('size', '?')
    plat = meta.get('platform', '?')
    sha = meta.get('sha256', None)
    lic = meta.get('license', 'unknown')
    sig = meta.get('signature', 'unknown')
    dl_rel = meta.get('download_url')

    details = u"Название: {t}\nВерсия: {v}\nПлатформа: {p}\nРазмер: {s}\nЛицензия: {l}\nПодпись: {sg}\nSHA-256: {h}".format(
        t=title, v=ver, p=plat, s=size, l=lic, sg=sig, h=sha or "—")

    if py_s60:
        pys60_note(details)
        proceed = appuifw.query(u"Скачать и подготовить для установки?", "query")
        if not proceed:
            return
    else:
        print("=== Details ===")
        print(details)
        ok = input("Download and prepare for install? (y/N): ").strip().lower()
        if ok != "y":
            return

    # Build download URL and target path
    if not dl_rel:
        if py_s60:
            pys60_note(u"Нет download_url в метаданных.")
        else:
            print("No download URL in metadata")
        return
    dl_url = server_url + dl_rel
    fname = os.path.basename(dl_rel)
    dest_dir = get_device_download_folder()
    dest_path = os.path.join(dest_dir, fname)

    # Download with progress
    try:
        if py_s60:
            # show simple progress via successive notes
            def on_progress(downloaded, total):
                if total:
                    perc = int(downloaded * 100 / total)
                    appuifw.note(u"Downloading: %d%%" % perc)
                else:
                    appuifw.note(u"Downloaded: %d bytes" % downloaded)
        else:
            def on_progress(downloaded, total):
                if total:
                    perc = int(downloaded * 100 / total)
                    print("\rDownloading: %d%% (%d/%d)" % (perc, downloaded, total), end="", flush=True)
                else:
                    print("\rDownloaded: %d bytes" % downloaded, end="", flush=True)

        download_with_progress(dl_url, dest_path, on_progress=on_progress)
        if not py_s60:
            print("\nDownload finished:", dest_path)
    except Exception as e:
        if py_s60:
            pys60_note(u"Ошибка скачивания: %s" % unicode_safe(e))
        else:
            print("Download failed:", e)
        return

    # Compute SHA-256
    try:
        if py_s60:
            pys60_note(u"Вычисление SHA-256 ...")
        else:
            print("Computing SHA-256 ...")
        local_hash = sha256_of_path(dest_path)
    except Exception as e:
        if py_s60:
            pys60_note(u"Ошибка хеширования: %s" % unicode_safe(e))
        else:
            print("Hashing failed:", e)
        return

    # Compare with metadata
    match = (local_hash.lower() == (sha or "").lower()) if sha else None
    if py_s60:
        if sha:
            pys60_note(u"SHA-256 на сервере: %s\nЛокальный SHA-256: %s\nСовпадение: %s" % (sha, local_hash, u"ДА" if match else u"НЕТ"))
        else:
            pys60_note(u"Локальный SHA-256: %s\n(в метаданных нет контрольной суммы)" % local_hash)
    else:
        print("Server SHA-256:", sha)
        print("Local SHA-256 :", local_hash)
        if sha:
            print("MATCH:" , "YES" if match else "NO")

    # Try to launch installer
    launched = try_launch_installer(dest_path)
    if launched:
        if py_s60:
            pys60_note(u"Попытка запустить установку выполнена.")
        else:
            print("Attempted to launch installer.")
    else:
        note = u"Файл сохранён: %s\nЗапустите установку вручную через менеджер приложений или перенесите файл на устройство." % dest_path
        if py_s60:
            pys60_note(note)
        else:
            print(note)

# Entry point
def main():
    parser = argparse.ArgumentParser(description="Reloaded Nokia Client (PyS60 + console)")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000", help="Base URL of repository server")
    args = parser.parse_args()
    client_flow(args.server_url)

if __name__ == "__main__":
    main()
