from multiprocessing import Process
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import subprocess
import requests
import json
import shutil
import glob

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_PATH, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PROFILES_ROOT = os.environ.get("PROFILES_ROOT") or os.path.join(DATA_DIR, "chrome_profiles")
PROFILES_ROOT = os.path.abspath(PROFILES_ROOT)
os.makedirs(PROFILES_ROOT, exist_ok=True)

SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
NOTIF_DIR = os.path.join(DATA_DIR, "notif_markers")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(NOTIF_DIR, exist_ok=True)

# email.txt (optional untuk label saja)
EMAIL_FILE = os.path.join(DATA_DIR, "email.txt")

# ✅ status file untuk panel (dibaca agent.py)
STATUS_FILE = os.path.join(DATA_DIR, "loop_status.json")

# ✅ loop log file (untuk truncate tiap 5 menit)
LOOP_LOG_FILE = os.path.join(DATA_DIR, "loop_log.txt")

# Delay & timing
PRE_OPEN_DELAY = int(os.environ.get("PRE_OPEN_DELAY", "2"))          # delay sebelum get(link)
START_PROFILE_DELAY = int(os.environ.get("START_PROFILE_DELAY", "2"))
SLEEP_SEBELUM_AKSI = int(os.environ.get("SLEEP_SEBELUM_AKSI", "2"))
SLEEP_SESUDAH_AKSI = int(os.environ.get("SLEEP_SESUDAH_AKSI", "25"))
SLEEP_JIKA_ERROR = int(os.environ.get("SLEEP_JIKA_ERROR", "2"))

# ✅ NEW: delay setelah selesai 1 putaran link milik profile, lalu ulang dari awal
SLEEP_AFTER_FULL_ROUND = int(os.environ.get("SLEEP_AFTER_FULL_ROUND", "2"))

# Default paling aman 1 (naikin kalau server kuat)
MAX_PARALLEL = int(os.environ.get("MAX_PARALLEL", "25"))

# ======================
# PEMBAGIAN LINK PER FILE/GRUP CLONE
# Contoh: CLONES_PER_FILE=4
# - clone joko1-joko4   -> baca joko1.txt
# - clone joko5-joko8   -> baca joko2.txt
# - clone joko9-joko12  -> baca joko3.txt
# dst
# Total link di setiap jokoX.txt akan dibagi berdasarkan jumlah clone di grup itu
# ======================
CLONES_PER_FILE = int(os.environ.get("CLONES_PER_FILE", "10"))

# Chrome profile directory di dalam user-data-dir (biasanya Default)
PROFILE_DIR = os.environ.get("PROFILE_DIR", "Default")

# Telegram (optional)
TG_TOKEN = os.environ.get("TG_TOKEN", "8333206393:AAG8Z76SSbgAEAC1a3oPT8XhAF9t_rDOq3A").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "-1003532458425").strip()

# ✅ LOG TRUNCATE tiap 5 menit
LOG_TRUNCATE_SECONDS = 300  # 5 menit

# ✅ QUIET HOURS LOOP (WITA Makassar)
AUTO_TIMEZONE = os.environ.get("AUTO_TIMEZONE", "Asia/Makassar")
WITA_TZ = ZoneInfo(AUTO_TIMEZONE)
PAUSE_START_HOUR = 3
PAUSE_START_MINUTE = 25
PAUSE_END_HOUR = 6
PAUSE_END_MINUTE = 1


# ======================
# TELEGRAM HELPERS
# ======================
def tg_enabled():
    return bool(TG_TOKEN and TG_CHAT_ID)

def tg_send_message(text: str):
    if not tg_enabled():
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": text}, timeout=15)
    except:
        pass

def tg_send_photo(photo_path: str, caption: str):
    if not tg_enabled():
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as f:
            requests.post(url, data={"chat_id": TG_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=30)
    except:
        pass


# ======================
# TIME / QUIET HOURS HELPERS
# ======================
def now_wita():
    return datetime.now(WITA_TZ)

def format_wita(dt_obj=None):
    dt_obj = dt_obj or now_wita()
    return dt_obj.strftime("%Y-%m-%d %H:%M:%S WITA")

def in_pause_window(dt_obj=None):
    dt_obj = dt_obj or now_wita()
    minute_now = dt_obj.hour * 60 + dt_obj.minute
    start_minute = PAUSE_START_HOUR * 60 + PAUSE_START_MINUTE
    end_minute = PAUSE_END_HOUR * 60 + PAUSE_END_MINUTE
    return start_minute <= minute_now < end_minute

def seconds_until_resume(dt_obj=None):
    dt_obj = dt_obj or now_wita()
    resume_dt = dt_obj.replace(hour=PAUSE_END_HOUR, minute=PAUSE_END_MINUTE, second=0, microsecond=0)
    if dt_obj >= resume_dt:
        resume_dt = resume_dt + timedelta(days=1)
    sec = int((resume_dt - dt_obj).total_seconds())
    return max(sec, 1)

def notification_marker_path(kind: str, date_key: str) -> str:
    safe_kind = (kind or "event").replace("/", "_").replace(" ", "_")
    return os.path.join(NOTIF_DIR, f".notif_{safe_kind}_{date_key}.flag")

def send_once_per_day(kind: str, text: str):
    if not tg_enabled():
        return
    now_dt = now_wita()
    date_key = now_dt.strftime("%Y%m%d")
    if kind == "resume" and now_dt.hour < PAUSE_END_HOUR:
        date_key = (now_dt - timedelta(days=1)).strftime("%Y%m%d")
    marker = notification_marker_path(kind, date_key)
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(format_wita(now_dt))
        tg_send_message(text)
    except FileExistsError:
        pass
    except Exception:
        pass

def force_close_all_chrome():
    cmds = [
        ["pkill", "-f", "chromedriver"],
        ["pkill", "-f", "chrome"],
        ["pkill", "-f", "chromium"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

# ======================
# STATUS (per profile)
# ======================
def _now():
    return format_wita()

def _safe_read_json(path, default=None):
    if default is None:
        default = {}
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return json.load(f)
    except Exception:
        return default

def _safe_write_json(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass

def update_status(profile_name: str, **kwargs):
    data = _safe_read_json(STATUS_FILE, default={})
    if not isinstance(data, dict):
        data = {}
    st = data.get(profile_name) if isinstance(data.get(profile_name), dict) else {}
    st.update(kwargs)
    st["last_update"] = _now()
    data[profile_name] = st
    _safe_write_json(STATUS_FILE, data)


# ======================
# FILE HELPERS
# ======================
def read_file_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]

def read_emails(path):
    """
    email.txt format:
    akun1@gmail.com|pass
    akun2@gmail.com|pass
    return list of email only (order)
    """
    emails = []
    for line in read_file_lines(path):
        if "|" in line:
            emails.append(line.split("|", 1)[0].strip())
        else:
            emails.append(line.strip())
    return emails


# ======================
# PROFILE SCAN (jokoX folders)
# ======================
def scan_joko_folders(profiles_root: str):
    out = []
    if not os.path.isdir(profiles_root):
        return out

    found = []
    for name in os.listdir(profiles_root):
        full = os.path.join(profiles_root, name)
        if not os.path.isdir(full):
            continue
        low = name.lower()
        if not low.startswith("joko"):
            continue
        num = name[4:]
        if num.isdigit():
            found.append((int(num), name, full))

    found.sort(key=lambda x: x[0])
    for _, name, full in found:
        out.append({
            "name": name,
            "user_data_dir": full,
            "profile_dir": PROFILE_DIR,
        })
    return out


# ======================
# LOCK (anti profile in use)
# ======================
def lock_path_for_user_data_dir(user_data_dir: str) -> str:
    safe = user_data_dir.replace("/", "_").replace(" ", "_")
    return os.path.join(BASE_PATH, f".lock_{safe}.pid")

def acquire_profile_lock(user_data_dir: str) -> bool:
    lp = lock_path_for_user_data_dir(user_data_dir)
    try:
        if os.path.exists(lp):
            try:
                old_pid = int(open(lp, "r").read().strip() or "0")
            except:
                old_pid = 0
            if old_pid > 0:
                try:
                    os.kill(old_pid, 0)
                    return False
                except:
                    pass
        with open(lp, "w") as f:
            f.write(str(os.getpid()))
        return True
    except:
        return False

def release_profile_lock(user_data_dir: str):
    lp = lock_path_for_user_data_dir(user_data_dir)
    try:
        if os.path.exists(lp):
            os.remove(lp)
    except:
        pass


# ======================
# CHROME OPTIONS
# ======================
def get_options(user_data_dir: str, profile_dir: str):
    options = webdriver.ChromeOptions()

    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f"--profile-directory={profile_dir or 'Default'}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--window-size=900,720")

    options.add_argument("--restore-last-session")

    # ✅ anti sync / chrome sign-in prompt
    options.add_argument("--disable-sync")
    options.add_argument("--disable-features=SyncPromo,SigninPromo")

    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,

            # ✅ reduce sync/signin prompts
            "sync_promo.show_on_first_run": False,
            "signin.allowed": False,
        },
    )

    # ==============================
    # 🔥 EXTRA STABILITY SETTINGS (ADDED)
    # ==============================
    options.add_argument("--test-type")
    options.add_argument("--simulate-outdated-no-au=Tue, 31 Dec 2099 23:59:59 GMT")
    options.add_argument("--disable-component-update")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")
    options.add_argument("--window-size=700,700")
    options.add_argument("--disable-extensions")
    # ✅ LIGHTWEIGHT / SMOOTH (tambahan saja)
    options.add_argument("--mute-audio")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-translate")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation", "enable-logging"]
    )
    options.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.exit_type": "Normal",
            "profile.exited_cleanly": True,
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.images": 2
        }
    )

    return options


# ======================
# SCREENSHOT
# ======================
def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def save_screenshot(driver, profile_name, prefix="SHOT"):
    ensure_dir(SCREENSHOT_DIR)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(SCREENSHOT_DIR, f"{prefix}_{profile_name}_{ts}.png")
    try:
        driver.save_screenshot(out)
        return out
    except:
        return ""

def save_fail_screenshot(driver, profile_name, prefix="FAIL"):
    return save_screenshot(driver, profile_name, prefix=prefix)

def tg_notify_open_workspace_error(driver, profile_name, email, link, idx, total, round_num, err, stage="OPEN_WORKSPACE"):
    caption = (
        "❌ OPEN WORKSPACE ERROR\n"
        f"Stage: {stage}\n"
        f"Profile: {profile_name}\n"
        f"Email: {email}\n"
        f"Round: {round_num}\n"
        f"Index: {idx}/{total}\n"
        f"Link: {link}\n"
        f"Error: {type(err).__name__}: {str(err)[:220]}"
    )
    try:
        shot = save_fail_screenshot(driver, profile_name, prefix="OPEN_WORKSPACE_FAIL") if driver else ""
        if shot:
            tg_send_photo(shot, caption)
        else:
            tg_send_message(caption)
    except:
        pass
    try:
        update_status(profile_name, state="ERROR_OPEN_WORKSPACE", last_error=caption[:260])
    except:
        pass

def clear_browser_cache_after_round(driver, user_data_dir: str):
    """
    Bersihkan cache browser selesai 1 putaran semua link.
    Aman untuk clone profile yang sudah login: jangan hapus cookies/session/login.
    Yang dibersihkan hanya cache/temp browser.
    """
    try:
        if driver:
            try:
                driver.execute_cdp_cmd("Network.enable", {})
            except:
                pass
            try:
                driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            except:
                pass
            try:
                driver.execute_script("""
                    try {
                        if (window.caches) {
                            caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
                        }
                    } catch(e) {}
                """)
            except:
                pass
    except:
        pass

    try:
        cleanup_profile_cache(user_data_dir)
    except:
        pass


# ======================
# LOOP LOG TRUNCATE
# ======================
def truncate_loop_log_if_needed(state):
    """
    state: dict with 'last_trunc'
    """
    try:
        now = time.time()
        last = state.get("last_trunc", 0)
        if now - last >= LOG_TRUNCATE_SECONDS:
            # truncate file
            try:
                with open(LOOP_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
            except:
                pass
            state["last_trunc"] = now
    except:
        pass


# ======================
# ✅ RECOVERY HELPERS (NEW)
# ======================
def _rm_path(p: str):
    try:
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            os.remove(p)
    except:
        pass

def cleanup_profile_cache(user_data_dir: str):
    """
    Hapus cache Chrome di user_data_dir agar clone yang crash bisa bersih.
    Tetap aman untuk profile login: jangan hapus Cookies, Local Storage,
    Session Storage, Sessions, WebStorage, atau data akun lain.
    """
    try:
        candidates = [
            os.path.join(user_data_dir, "Default", "Cache"),
            os.path.join(user_data_dir, "Default", "Code Cache"),
            os.path.join(user_data_dir, "Default", "GPUCache"),
            os.path.join(user_data_dir, "Default", "DawnCache"),
            os.path.join(user_data_dir, "Default", "GrShaderCache"),
            os.path.join(user_data_dir, "Default", "GraphiteDawnCache"),
            os.path.join(user_data_dir, "Default", "Service Worker", "CacheStorage"),
            os.path.join(user_data_dir, "Default", "Service Worker", "ScriptCache"),
            os.path.join(user_data_dir, "Crashpad"),
        ]
        for p in candidates:
            _rm_path(p)

        # kadang cache ada di root
        for p in ["Cache", "Code Cache", "GPUCache", "DawnCache", "GrShaderCache", "GraphiteDawnCache"]:
            _rm_path(os.path.join(user_data_dir, p))

        # buang file crash/log temp yang kadang bikin hang
        for pattern in [
            os.path.join(user_data_dir, "*.tmp"),
            os.path.join(user_data_dir, "*.log"),
        ]:
            for fp in glob.glob(pattern):
                _rm_path(fp)

        # bersihin tmp chrome yang sering ngunci
        for pattern in [
            "/tmp/.com.google.Chrome*",
            "/tmp/.org.chromium.Chromium*",
        ]:
            for fp in glob.glob(pattern):
                _rm_path(fp)
    except:
        pass


# ======================
# LINK WORK
# ======================
def process_single_link(driver, profile_name, email, link, idx, total, round_num):
    # update status (start open link)
    update_status(
        profile_name,
        state="RUNNING",
        round_num=round_num,
        link_idx=idx,
        link_total=total,
        current_link=link,
        last_error=""
    )


    try:
        time.sleep(PRE_OPEN_DELAY)

        driver.get(link)
        wait = WebDriverWait(driver, 12)

        # klik trust / open workspace kalau ada
        try:
            trust = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'I trust the owner')]")))
            trust.click()
        except:
            pass

        # ============================
        # 🔥 OPEN WORKSPACE (NOTIF + SCREENSHOT kalau error di step ini)
        # ============================
        try:
            open_ws = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Open Workspace')]")))
            try:
                open_ws.click()
            except Exception as e_click:
                tg_notify_open_workspace_error(
                    driver, profile_name, email, link, idx, total, round_num, e_click, stage="CLICK_OPEN_WORKSPACE"
                )
        except Exception as e_open_ws:
            tg_notify_open_workspace_error(
                driver, profile_name, email, link, idx, total, round_num, e_open_ws, stage="FIND_OPEN_WORKSPACE"
            )

        # tunggu iframe IDE (kalau link Firebase Studio)
        try:
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe.the-iframe.is-loaded[src*='ide-start']")))
        except:
            pass

        time.sleep(SLEEP_SEBELUM_AKSI)

        try:
            driver.find_element(By.TAG_NAME, "body").click()
        except:
            pass

        try:
            actions = ActionChains(driver)
            actions.key_down(Keys.CONTROL).send_keys("`").key_up(Keys.CONTROL).perform()
        except:
            pass

        time.sleep(SLEEP_SESUDAH_AKSI)


        update_status(profile_name, state="RUNNING", last_error="")
        return True, ""

    except Exception as e:
        err = f"{type(e).__name__}: {str(e)}"
        print(f"[{profile_name}] LINK GAGAL DIBUKA: {err}")
        update_status(profile_name, state="ERROR", last_error=err[:260])
        time.sleep(SLEEP_JIKA_ERROR)
        return False, err


# ======================
# WORKER (1 profile = 1 chrome, NEVER CLOSE, LOOP BACK)
# ======================
def worker(profile_name, email, user_data_dir, profile_dir, total_slots, group_counts):
    if not acquire_profile_lock(user_data_dir):
        msg = f"⚠️ SKIP: profile sedang dipakai proses lain: {profile_name}\nuser_data_dir={user_data_dir}"
        print(msg)
        if tg_enabled():
            tg_send_message(msg)
        update_status(profile_name, state="SKIP_LOCK", last_error="profile lock aktif")
        return

    driver = None
    try:
        # ✅ ambil nomor profile dari nama (jokoX -> X)
        prof_num = 0
        try:
            low = (profile_name or "").lower()
            if low.startswith("joko"):
                tail = low[4:]
                if tail.isdigit():
                    prof_num = int(tail)
        except Exception:
            prof_num = 0

        # ==============================
        # ✅ Mapping file link per jumlah clone yang dipakai per file
        # Contoh CLONES_PER_FILE=4:
        # 1-4   -> joko1.txt
        # 5-8   -> joko2.txt
        # 9-12  -> joko3.txt
        # dst...
        # ==============================
        group_size = CLONES_PER_FILE if CLONES_PER_FILE > 0 else 1
        group_idx = ((prof_num - 1) // group_size) + 1 if prof_num > 0 else 1
        local_num = ((prof_num - 1) % group_size) + 1 if prof_num > 0 else 1
        shared_link_file = os.path.join(DATA_DIR, f"joko{group_idx}.txt")

        # ✅ group_slots = jumlah clone yg benar-benar ada di group itu
        group_slots = int(group_counts.get(group_idx, group_size) or group_size)
        if group_slots <= 0:
            group_slots = 1

        # state untuk truncate log
        log_state = {"last_trunc": 0}

        update_status(profile_name, state="RUNNING", round_num=0, link_idx=0, link_total=0, current_link="", last_error="")

        def handle_pause_window(current_round_num):
            nonlocal driver

            if not in_pause_window():
                return False

            stop_text = (
                "🛑 LOOP STOP OTOMATIS\\n"
                f"Waktu: {format_wita()}\\n"
                f"Timezone auto-detect: {AUTO_TIMEZONE}\\n"
                "Jadwal stop: 03:25-05:25 WITA Makassar\\n"
                "Action: stop aktifitas loop dan close all Chrome / quit Chrome."
            )
            send_once_per_day("stop", stop_text)

            try:
                if driver:
                    driver.quit()
            except:
                pass
            driver = None

            force_close_all_chrome()

            update_status(
                profile_name,
                state="PAUSED_SCHEDULE",
                round_num=current_round_num,
                link_idx=0,
                current_link="",
                last_error=f"Paused by schedule until 05:25 WITA | {format_wita()}"[:260],
            )

            sleep_seconds = seconds_until_resume()
            while sleep_seconds > 0:
                time.sleep(min(30, sleep_seconds))
                if not in_pause_window():
                    break
                sleep_seconds = seconds_until_resume()

            resume_text = (
                "▶️ LOOP START LAGI OTOMATIS\\n"
                f"Waktu: {format_wita()}\\n"
                f"Timezone auto-detect: {AUTO_TIMEZONE}\\n"
                "Action: aktifitas loop berjalan lagi seperti biasa."
            )
            send_once_per_day("resume", resume_text)
            update_status(profile_name, state="RESUMING_SCHEDULE", last_error="")
            return True

        # =========================================================
        # ✅ AUTO-RECOVERY LOOP (NEW):
        # kalau driver crash / error berat -> close, hapus cache, start lagi
        # =========================================================
        round_num = 0
        while True:
            try:
                if handle_pause_window(round_num):
                    continue

                # start driver kalau belum ada
                if driver is None:
                    options = get_options(user_data_dir, profile_dir)
                    driver = webdriver.Chrome(options=options)
                    print(f"[{profile_name}] ({email}) Chrome started | user_data_dir={user_data_dir}")

                round_num += 1

                # ✅ hapus loop log tiap 5 menit
                truncate_loop_log_if_needed(log_state)

                links = read_file_lines(shared_link_file)
                total_links = len(links)

                if local_num <= 0 or local_num > group_slots:
                    print(f"[{profile_name}] ROUND#{round_num} IDLE: local_num={local_num} di luar group_slots={group_slots} (sleep 10s)")
                    update_status(profile_name, state="IDLE_NO_LINKS", round_num=round_num, link_idx=0, link_total=total_links, current_link="")
                    time.sleep(10)
                    continue

                if total_links == 0:
                    print(f"[{profile_name}] ROUND#{round_num} IDLE: {os.path.basename(shared_link_file)} kosong / tidak ada (sleep 10s)")
                    update_status(profile_name, state="IDLE_NO_LINKS", round_num=round_num, link_idx=0, link_total=0, current_link="")
                    time.sleep(10)
                    continue

                if local_num > total_links:
                    print(f"[{profile_name}] ROUND#{round_num} IDLE: tidak ada link untuk local_num={local_num}, total_links={total_links} file={os.path.basename(shared_link_file)} (sleep 10s)")
                    update_status(profile_name, state="IDLE_NO_LINKS", round_num=round_num, link_idx=0, link_total=total_links, current_link="")
                    time.sleep(10)
                    continue

                # ✅ DISTRIBUSI STRIDE SESUAI group_slots:
                # slot i buka link i, i+group_slots, i+2*group_slots, ...
                start_index = local_num - 1
                indices = list(range(start_index, total_links, group_slots))

                print(f"[{profile_name}] ROUND#{round_num} file={os.path.basename(shared_link_file)} total_links={total_links} group_slots={group_slots} assigned={len(indices)}")
                update_status(profile_name, state="RUNNING", round_num=round_num, link_idx=0, link_total=total_links, current_link="", last_error="")

                for link_i in indices:
                    if handle_pause_window(round_num):
                        break

                    # ✅ hapus loop log tiap 5 menit (jaga kalau loop panjang)
                    truncate_loop_log_if_needed(log_state)

                    link = links[link_i]
                    global_idx = link_i + 1  # 1-based line number in jokoX.txt

                    print(f"[{profile_name}] ROUND#{round_num} OPEN #{global_idx}/{total_links} ({os.path.basename(shared_link_file)}): {link}")

                    # proses link biasa
                    ok, err = process_single_link(driver, profile_name, email, link, global_idx, total_links, round_num)
                    if not ok:
                        print(f"[{profile_name}] GAGAL: {link} -> {err}")

                try:
                    clear_browser_cache_after_round(driver, user_data_dir)
                    print(f"[{profile_name}] Cache browser dibersihkan setelah semua link selesai dibuka.")
                except Exception as e_cache:
                    print(f"[{profile_name}] Gagal bersihkan cache browser: {type(e_cache).__name__}: {e_cache}")

                print(f"[{profile_name}] ROUND#{round_num} selesai (assigned={len(indices)}). Ulang dari awal slot (sleep {SLEEP_AFTER_FULL_ROUND}s)...")
                update_status(profile_name, state="SLEEP_ROUND", round_num=round_num, link_idx=0, link_total=total_links, current_link="")
                time.sleep(SLEEP_AFTER_FULL_ROUND)

            except Exception as e:
                # ==============================
                # ✅ CRASH/ERROR RECOVERY (NEW)
                # ==============================
                err = f"{type(e).__name__}: {str(e)}"
                print(f"[{profile_name}] Worker crash (recovery): {err}")
                update_status(profile_name, state="CRASH_RECOVERING", last_error=err[:240])

                # screenshot kalau masih sempat
                if tg_enabled():
                    caption = f"⚠️ LOOP CRASH\\nProfile: {profile_name}\\nEmail: {email}\\nError: {err[:300]}\\nAction: close clone + clear cache + restart"
                    try:
                        if driver:
                            shot = save_fail_screenshot(driver, profile_name, prefix="CRASH")
                            if shot:
                                tg_send_photo(shot, caption)
                            else:
                                tg_send_message(caption)
                        else:
                            tg_send_message(caption)
                    except:
                        pass

                # close driver
                try:
                    if driver:
                        driver.quit()
                except:
                    pass
                driver = None

                # clear cache profile ini
                try:
                    cleanup_profile_cache(user_data_dir)
                except:
                    pass

                # tunggu sebentar lalu lanjut (akan start driver lagi)
                time.sleep(max(3, SLEEP_JIKA_ERROR))
                continue

    except Exception as e:
        print(f"[{profile_name}] Worker fatal crash: {type(e).__name__}: {e}")
        if tg_enabled():
            tg_send_message(f"⚠️ Worker fatal crash: {profile_name} ({email})\\n{type(e).__name__}: {e}")
        update_status(profile_name, state="CRASH", last_error=f"{type(e).__name__}: {str(e)[:240]}")

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        release_profile_lock(user_data_dir)
        update_status(profile_name, state="STOPPED")


# ======================
# MAIN
# ======================
if __name__ == "__main__":
    profiles = scan_joko_folders(PROFILES_ROOT)
    if not profiles:
        print(f"⚠️ Tidak ada folder 'jokoX' di {PROFILES_ROOT}. Jalankan login.py dulu.")
        time.sleep(10)
        raise SystemExit(0)

    # slot yang benar-benar dijalankan
    total_slots = min(len(profiles), MAX_PARALLEL) if MAX_PARALLEL > 0 else len(profiles)

    emails = read_emails(EMAIL_FILE)
    while len(emails) < len(profiles):
        emails.append("unknown@email")

    # ✅ hitung jumlah profile per group (untuk pembagian link sesuai jumlah clone yang ada)
    # yang dihitung hanya yang benar-benar akan dijalankan (<= total_slots)
    group_counts = {}
    started_profiles = profiles[:total_slots]

    for prof in started_profiles:
        name = (prof.get("name") or "").lower()
        n = 0
        if name.startswith("joko"):
            tail = name[4:]
            if tail.isdigit():
                n = int(tail)
        if n <= 0:
            continue
        group_size = CLONES_PER_FILE if CLONES_PER_FILE > 0 else 1
        group_idx = ((n - 1) // group_size) + 1
        group_counts[group_idx] = group_counts.get(group_idx, 0) + 1

    procs = []
    started = 0

    for idx, prof in enumerate(profiles):
        if started >= total_slots:
            break

        profile_name = prof["name"]
        user_data_dir = prof["user_data_dir"]
        profile_dir = prof["profile_dir"]
        email = emails[idx] if idx < len(emails) else ""

        p = Process(target=worker, args=(profile_name, email, user_data_dir, profile_dir, total_slots, group_counts))
        p.start()
        procs.append(p)

        started += 1
        time.sleep(START_PROFILE_DELAY)

    for p in procs:
        p.join()