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

# --- 1. NEW HOOK THING (Your Version) ---
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

# --- 2. OLD MOVEMENT SCRIPT (As requested) ---
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

# --- 3. NEW MEMORY STUFF (Fixed) ---
def perform_memory_cleanup(d):
    try:
        logging.info("🧹 Aggressive Memory Cleanup Initiated...")
        # Force V8 GC (needs --expose-gc)
        d.execute_script("if(window.gc){window.gc();}")
        # Clear Network Cache
        d.execute_cdp_cmd("Network.clearBrowserCache", {})
        # Use HeapProfiler (The fix for the 'Memory.forcedGC not found' error)
        try:
            d.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
        except: pass
        d.execute_script("console.clear();")
    except Exception as e:
        logging.warning(f"Cleanup non-critical error: {e}")

# --- BROWSER SETUP ---
def setup_driver():
    logging.info("Launching Stable Browser...")
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    
    # Memory and GC exposure flags
    chrome_options.add_argument("--js-flags='--expose-gc --max-old-space-size=512'")
    chrome_options.add_argument("--enable-low-end-device-mode") 
    chrome_options.add_argument("--renderer-process-limit=1")
    
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    
    # Inject your new Hook
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": WASM_HOOK_SCRIPT
    })
    return d

# --- FLASK & UTILS ---
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
        
        # Play Anonymously (Guest)
        try:
            guest_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
            driver.execute_script("arguments[0].click();", guest_btn)
        except: pass

        logging.info("Injecting Old Movement Script...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        logging.info("✅ Bot Active.")
        
        while True:
            time.sleep(30)
            # Run the new memory cleanup every 10 mins
            if time.time() - last_cleanup > 600:
                perform_memory_cleanup(driver)
                last_cleanup = time.time()
            
            # Simple title check to ensure browser is still alive
            _ = driver.title

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
            logging.error("Restarting main loop...")
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
