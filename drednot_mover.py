import os
import time
import logging
import threading
import gc
import sys
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- CONFIGURATION ---
SHIP_INVITE_LINK = 'https://drednot.io/invite/-EKifhVqXiiFGvEx9JvGnC9H' 
ANONYMOUS_LOGIN_KEY = '_M85tFxFxIRDax_nh-HYm1gT' 
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- 1. YOUR WASM HOOK ---
WASM_HOOK_SCRIPT = """
(function() {
    'use strict';
    console.log('[Wasm Hook] Initializing isTrusted bypass...');
    const win = window;
    const originalInstantiate = win.WebAssembly.instantiate;
    const originalInstantiateStreaming = win.WebAssembly.instantiateStreaming;

    function patchImports(importObject) {
        if (!importObject || !importObject.wbg) return;
        Object.keys(importObject.wbg).forEach(key => {
            if (key.includes('isTrusted')) {
                console.log(`[Wasm Hook] DETECTED: ${key}. Overriding to force true.`);
                importObject.wbg[key] = function(eventPtr) {
                    return 1;
                };
            }
        });
    }

    win.WebAssembly.instantiate = function(bufferSource, importObject) {
        if (importObject) patchImports(importObject);
        return originalInstantiate.apply(this, arguments);
    };

    win.WebAssembly.instantiateStreaming = function(source, importObject) {
        if (importObject) patchImports(importObject);
        return originalInstantiateStreaming.apply(this, arguments);
    };
})();
"""

# --- 2. YOUR OLD MOVEMENT SCRIPT ---
JS_MOVEMENT_SCRIPT = """
console.log("[Bot] Starting Movement Loop...");
let toggle = true;
function press(key, type) {
    const kCode = (key === 'a') ? 65 : 68;
    const eventObj = {
        key: key, code: 'Key' + key.toUpperCase(),
        keyCode: kCode, which: kCode,
        bubbles: true, cancelable: true, view: window, repeat: type === 'keydown'
    };
    const ev = new KeyboardEvent(type, eventObj);
    document.dispatchEvent(ev);
    window.dispatchEvent(ev);
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

// Background Janitor: Remove DOM bloat every 30s
setInterval(() => {
    ['.chat-container', '.ad-container', 'iframe', '.social-links'].forEach(s => {
        document.querySelectorAll(s).forEach(el => el.remove());
    });
}, 30000);
"""

# --- 3. NEW MEMORY CLEANUP (Fixed) ---
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

# --- 4. BROWSER SETUP (Stable Debian) ---
def setup_driver():
    logging.info("🚀 Launching Stable Chromium...")
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    
    # Aggressive memory saving
    chrome_options.add_argument("--window-size=120,120")
    chrome_options.add_argument("--js-flags=--expose-gc --max-old-space-size=400")
    chrome_options.add_argument("--renderer-process-limit=1")
    
    # Anti-Throttling
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-background-timer-throttling")
    
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    
    # Inject Hook
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WASM_HOOK_SCRIPT})
    return d

def start_bot():
    driver = setup_driver()
    wait = WebDriverWait(driver, 45)
    last_cleanup = time.time()
    
    try:
        logging.info(f"📍 Navigating: {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        
        # 1. Accept Invite
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")))
        driver.execute_script("arguments[0].click();", accept_btn)
        time.sleep(5)
        
        # 2. KEY LOGIN (Added Back)
        if ANONYMOUS_LOGIN_KEY:
            try:
                logging.info("🔑 Logging in with Anonymous Key...")
                restore_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Restore old anonymous key')]")))
                driver.execute_script("arguments[0].click();", restore_link)
                
                key_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-window input")))
                key_input.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", key_input)
                time.sleep(1)
                
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'modal-window')]//button[text()='Submit']")))
                driver.execute_script("arguments[0].click();", submit_btn)
                logging.info("✅ Key Submitted.")
                time.sleep(5)
            except Exception as e:
                logging.warning(f"Key login skip: {e}")

        # 3. Play
        try:
            play_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play')]")))
            driver.execute_script("arguments[0].click();", play_btn)
        except: pass

        # 4. Movement
        logging.info("⌨️ Injecting Movement...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        logging.info("✅ BOT ACTIVE")
        
        while True:
            time.sleep(60)
            # Cleanup every 5 mins
            if time.time() - last_cleanup > 300:
                perform_memory_cleanup(driver)
                last_cleanup = time.time()
            logging.info("💓 Heartbeat: Alive")
            _ = driver.title

    except Exception as e:
        logging.error(f"❌ Crash: {e}")
        raise
    finally:
        if driver:
            driver.quit()

# --- FLASK ---
flask_app = Flask('')
@flask_app.route('/')
def health(): return "OK"

def main():
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    while True:
        try:
            start_bot()
        except:
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
