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
from selenium.webdriver.common.action_chains import ActionChains

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

# --- 2. IMPROVED MOVEMENT SCRIPT (Added Focus + KeyCodes) ---
JS_MOVEMENT_SCRIPT = """
console.log("[Bot] Initializing Movement...");

// Force focus on the game canvas
const canvas = document.querySelector('canvas');
if (canvas) {
    canvas.focus();
    canvas.click();
}

function press(key, type) {
    const code = key === 'a' ? 65 : 68;
    const eventObj = {
        key: key, 
        code: 'Key' + key.toUpperCase(),
        keyCode: code,
        which: code,
        bubbles: true, 
        cancelable: true, 
        view: window, 
        repeat: type === 'keydown'
    };
    const ev = new KeyboardEvent(type, eventObj);
    document.dispatchEvent(ev);
    window.dispatchEvent(ev);
    if(canvas) canvas.dispatchEvent(ev);
}

if (window.botInterval) clearInterval(window.botInterval);
window.botInterval = setInterval(() => {
    press('a', 'keydown');
    setTimeout(() => press('a', 'keyup'), 100);
    setTimeout(() => {
        press('d', 'keydown');
        setTimeout(() => press('d', 'keyup'), 100);
    }, 200);
}, 400);
"""

# --- 3. UPDATED CLEANUP FUNCTION ---
def perform_memory_cleanup(d):
    try:
        logging.info("🧹 Performing Memory Cleanup...")
        d.execute_script("if(window.gc){window.gc();}")
        d.execute_cdp_cmd("Network.clearBrowserCache", {})
        try:
            d.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
        except: pass
        d.execute_script("console.clear();")
    except Exception as e:
        logging.warning(f"Cleanup error: {e}")

# --- BROWSER SETUP ---
def setup_driver():
    logging.info("Launching Optimized Browser...")
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1280,720") # Larger window helps focus
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    
    # CRITICAL: Prevent the browser from "pausing" the game loop in the background
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-background-timer-throttling")
    
    # Memory flags
    chrome_options.add_argument("--js-flags='--expose-gc --max-old-space-size=512'")
    chrome_options.add_argument("--enable-low-end-device-mode") 
    chrome_options.add_argument("--renderer-process-limit=1")
    
    prefs = {
        "profile.managed_default_content_settings.images": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WASM_HOOK_SCRIPT})
    return d

# --- FLASK ---
flask_app = Flask('')
@flask_app.route('/')
def health_check(): return "Bot Running"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def start_bot(use_key):
    driver = setup_driver()
    wait = WebDriverWait(driver, 40)
    last_cleanup = time.time()
    
    try:
        logging.info(f"Navigating: {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        
        # Accept Invite
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")))
        driver.execute_script("arguments[0].click();", accept_btn)
        time.sleep(5) 
        
        # Login Logic
        logged_in = False
        if use_key and ANONYMOUS_LOGIN_KEY:
            try:
                restore_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Restore old anonymous key')]")))
                driver.execute_script("arguments[0].click();", restore_link)
                inp = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.modal-window input[maxlength="24"]')))
                inp.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Submit']")))
                driver.execute_script("arguments[0].click();", submit_btn)
                logged_in = True
                time.sleep(3)
            except: pass
        
        if not logged_in:
            guest_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
            driver.execute_script("arguments[0].click();", guest_btn)
            
        # --- IMPORTANT: PHYSICAL FOCUS CLICK ---
        # We wait for the game canvas to exist, then click the center of it
        time.sleep(5)
        try:
            canvas = driver.find_element(By.TAG_NAME, "canvas")
            actions = ActionChains(driver)
            actions.move_to_element(canvas).click().perform()
            logging.info("Target focused via ActionChains.")
        except:
            logging.warning("Could not focus canvas via ActionChains.")

        logging.info("Injecting Movement Script...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        logging.info("✅ Bot Active.")
        
        while True:
            time.sleep(30)
            if time.time() - last_cleanup > 600:
                perform_memory_cleanup(driver)
                last_cleanup = time.time()
            
            # Re-inject focus and script every 5 minutes just in case
            if int(time.time()) % 300 < 31:
                driver.execute_script(JS_MOVEMENT_SCRIPT)

    except Exception as e:
        logging.error(f"Crash: {e}")
        raise
    finally:
        if driver:
            driver.quit()

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try:
            start_bot(use_key=True)
        except Exception:
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
