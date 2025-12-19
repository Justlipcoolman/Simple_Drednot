import os
import time
import logging
import threading
import gc
import requests
import traceback
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
SHIP_INVITE_LINK = 'https://drednot.io/invite/-EKifhVqXiiFGvEx9JvGnC9H' 
ANONYMOUS_LOGIN_KEY = '_M85tFxFxIRDax_nh-HYm1gT' 
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

# --- 1. WASM HOOK ---
WASM_HOOK_SCRIPT = """
(function() {
    'use strict';
    try {
        const win = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;
        function patchImports(importObject) {
            if (!importObject || !importObject.wbg) return;
            Object.keys(importObject.wbg).forEach(key => {
                if (key.includes('isTrusted')) {
                    importObject.wbg[key] = function() { return 1; };
                }
            });
        }
        const originalInstantiate = win.WebAssembly.instantiate;
        win.WebAssembly.instantiate = function(bufferSource, importObject) {
            if (importObject) patchImports(importObject);
            return originalInstantiate.apply(this, arguments);
        };
    } catch (e) {}
})();
"""

# --- 2. YOUR ORIGINAL MOVEMENT SCRIPT (RETAINED) ---
JS_MOVEMENT_SCRIPT = """
console.log("[Bot] Starting Movement Loop...");
let toggle = true;
function press(key, type) {
    const eventObj = {
        key: key, code: 'Key' + key.toUpperCase(),
        bubbles: true, cancelable: true, view: window, repeat: type === 'keydown'
    };
    document.dispatchEvent(new KeyboardEvent(type, eventObj));
    window.dispatchEvent(new KeyboardEvent(type, eventObj));
}
if (window.botInterval) clearInterval(window.botInterval);
window.botInterval = setInterval(() => {
    if (!toggle) return;
    press('a', 'keydown');
    setTimeout(() => press('a', 'keyup'), 100);
    setTimeout(() => {
        press('d', 'keydown');
        setTimeout(() => press('d', 'keyup'), 100);
    }, 200);
}, 400);
"""

# --- 3. UPDATED CLEANUP FUNCTION (FIXED ERROR) ---
def perform_memory_cleanup(d):
    """Forced memory purging using compatible 2025 commands."""
    try:
        logging.info("🧹 Aggressive Memory Cleanup Initiated...")
        
        # 1. Clear internal script memory (window.gc requires --expose-gc flag)
        d.execute_script("if(window.gc){window.gc();}")
        
        # 2. Clear browser caches
        d.execute_cdp_cmd("Network.clearBrowserCache", {})
        
        # 3. Fixed: Use HeapProfiler instead of the 'not found' Memory.forcedGC
        try:
            d.execute_cdp_cmd("HeapProfiler.enable", {})
            d.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
            d.execute_cdp_cmd("HeapProfiler.disable", {})
        except Exception:
            pass # Fallback if HeapProfiler is restricted
            
        # 4. Clear console to prevent log storage bloat
        d.execute_script("console.clear();")
        logging.info("✨ Cleanup complete.")
    except Exception as e:
        logging.warning(f"Cleanup non-critical error: {e}")

# --- BROWSER SETUP ---
def setup_driver():
    logging.info("Launching Optimized Browser (No-Restart Mode)...")
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    
    # Flags for Manual GC and Memory Limiting
    chrome_options.add_argument("--js-flags='--expose-gc --max-old-space-size=512'")
    chrome_options.add_argument("--enable-low-end-device-mode") 
    chrome_options.add_argument("--renderer-process-limit=1")
    chrome_options.add_argument("--disable-site-isolation-trials")
    
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WASM_HOOK_SCRIPT})
    return d

# --- FLASK & KEEP ALIVE ---
flask_app = Flask('')
@flask_app.route('/')
def health_check(): return "Bot Running"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def keep_alive():
    url = RENDER_EXTERNAL_URL or f"http://localhost:{os.environ.get('PORT', 10000)}"
    while True:
        time.sleep(60)
        try: requests.get(url, timeout=5)
        except: pass

def safe_click(d, element):
    try:
        d.execute_script("arguments[0].click();", element)
    except:
        element.click()

def start_bot(use_key):
    driver = setup_driver()
    wait = WebDriverWait(driver, 40)
    last_cleanup = time.time()
    
    try:
        logging.info(f"Navigating: {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        
        # Accept Invite
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")))
        safe_click(driver, accept_btn)
        time.sleep(5) 
        
        # Login Logic
        logged_in = False
        if use_key and ANONYMOUS_LOGIN_KEY:
            try:
                restore_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Restore old anonymous key')]")))
                safe_click(driver, restore_link)
                inp = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.modal-window input[maxlength="24"]')))
                inp.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Submit']")))
                safe_click(driver, submit_btn)
                logged_in = True
                time.sleep(2)
            except: pass
        
        if not logged_in:
            guest_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
            safe_click(driver, guest_btn)
            
        logging.info("Injecting Movement Script...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        logging.info("✅ Bot Active. No-Restart mode enabled.")
        
        while True:
            time.sleep(30)
            
            # Cleanup every 10 minutes to prevent RAM creep
            if time.time() - last_cleanup > 600:
                perform_memory_cleanup(driver)
                last_cleanup = time.time()
            
            _ = driver.title # Health check

    except Exception as e:
        logging.error(f"Crash: {e}")
        raise
    finally:
        if driver:
            driver.quit()

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    while True:
        try:
            start_bot(use_key=True)
        except Exception:
            logging.error("Restarting browser process...")
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
