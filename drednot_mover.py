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

# --- 1. NEW WASM HOOK THING ---
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

# --- 2. OLD MOVEMENT SCRIPT ---
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

# --- 3. NEW MEMORY STUFF ---
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
        logging.warning(f"Cleanup non-critical error: {e}")

def setup_driver():
    logging.info("🚀 Launching Chromium...")
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--js-flags=--expose-gc --max-old-space-size=512")
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WASM_HOOK_SCRIPT})
    return d

def start_bot():
    driver = setup_driver()
    wait = WebDriverWait(driver, 45)
    last_cleanup = time.time()
    
    try:
        logging.info(f"📍 Navigating to {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        
        # Step 1: Accept Invite
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")))
        driver.execute_script("arguments[0].click();", accept_btn)
        time.sleep(5)
        
        # Step 2: ADDED BACK - Login with Key
        if ANONYMOUS_LOGIN_KEY:
            try:
                logging.info("🔑 Attempting Login with Anonymous Key...")
                restore_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Restore old anonymous key')]")))
                driver.execute_script("arguments[0].click();", restore_link)
                
                # Enter key into the modal input
                key_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-window input")))
                key_input.send_keys(ANONYMOUS_LOGIN_KEY)
                
                # Force React/Wasm to detect the input text
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", key_input)
                time.sleep(1)
                
                # Click Submit inside the modal
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'modal-window')]//button[text()='Submit']")))
                driver.execute_script("arguments[0].click();", submit_btn)
                logging.info("✅ Key Login Submitted.")
                time.sleep(5)
            except Exception as e:
                logging.warning(f"⚠️ Key Login skip: {e}")

        # Step 3: Click Play Anonymously (Guest fallback)
        try:
            guest_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
            driver.execute_script("arguments[0].click();", guest_btn)
            logging.info("✔️ Playing...")
        except: 
            logging.info("Already in game.")

        # Step 4: Movement Script
        logging.info("⌨️ Injecting Movement...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        
        while True:
            time.sleep(60)
            if time.time() - last_cleanup > 600:
                perform_memory_cleanup(driver)
                last_cleanup = time.time()
            logging.info("💓 Heartbeat: Bot is moving")
            _ = driver.title # Check for crash

    except Exception as e:
        logging.error(f"❌ CRASH: {e}")
        raise
    finally:
        if driver:
            driver.quit()

# --- FLASK SERVER ---
flask_app = Flask('')
@flask_app.route('/')
def health(): return "Bot Running"

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
