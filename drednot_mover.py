# drednot_mover.py
# Optimization: "Trust Mode" - Assumes login success if buttons work.
# Does NOT wait for Chat/Canvas to appear to avoid timeouts.

import os
import time
import logging
import threading
import gc
import requests
from threading import Lock

from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
SHIP_INVITE_LINK = 'https://drednot.io/invite/mXC0XdWitXkiIgE2uzN7sRTO'
ANONYMOUS_LOGIN_KEY = '_M85tFxFxIRDax_nh-HYm1gT' 
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

# --- 1. WASM BYPASS ---
WASM_HOOK_SCRIPT = """
(function() {
    'use strict';
    const win = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;
    const originalInstantiate = win.WebAssembly.instantiate;
    const originalInstantiateStreaming = win.WebAssembly.instantiateStreaming;

    function patchImports(importObject) {
        if (!importObject || !importObject.wbg) return;
        Object.keys(importObject.wbg).forEach(key => {
            if (key.includes('isTrusted')) {
                importObject.wbg[key] = function() { return 1; };
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

# --- 2. MOVEMENT LOOP ---
JS_MOVEMENT_SCRIPT = """
console.log("[Bot] Injecting high-performance movement loop...");
let toggle = true;

function press(key, type) {
  document.dispatchEvent(
    new KeyboardEvent(type, {
      key: key,
      code: 'Key' + key.toUpperCase(),
      bubbles: true,
      cancelable: true,
      view: window
    })
  );
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

# --- GLOBAL STATE ---
driver = None

# --- BROWSER SETUP ---
def setup_driver():
    logging.info("Launching optimized headless browser...")
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--renderer-process-limit=2")
    chrome_options.add_argument("--js-flags=--expose-gc")
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": WASM_HOOK_SCRIPT
    })
    
    return d

# --- FLASK ---
flask_app = Flask('')
@flask_app.route('/')
def health_check():
    return "Bot Status: Running (Trust Mode)"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive_ping():
    url = RENDER_EXTERNAL_URL or f"http://localhost:{os.environ.get('PORT', 8080)}"
    logging.info(f"Monitor: {url}")
    while True:
        time.sleep(600)
        try: requests.get(url, timeout=5)
        except: pass

def safe_click(d, element):
    d.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    d.execute_script("arguments[0].click();", element)

# --- MAIN LOGIC ---
def start_bot(use_key_login):
    global driver
    driver = setup_driver()
    
    try:
        logging.info(f"Navigating to {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        wait = WebDriverWait(driver, 15)
        
        # Remove Ads
        try:
            driver.execute_script("const ads = document.querySelectorAll('a[href*=\"advertising\"], .ad-container, iframe'); ads.forEach(el => el.remove());")
        except: pass

        # 1. Accept Invite
        logging.info("Step 1: Accepting Invite...")
        join_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modal-container .btn-green")))
        safe_click(driver, join_btn)
        
        # 2. Login Sequence
        # We assume if these clicks work, we are logged in.
        # We do NOT wait for the game to load afterwards.
        if ANONYMOUS_LOGIN_KEY and use_key_login:
            try:
                logging.info("Step 2: Clicking 'Restore Key'...")
                short_wait = WebDriverWait(driver, 5)
                link = short_wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Restore old anonymous key')]")))
                safe_click(driver, link)
                
                logging.info("Step 3: Entering Key...")
                inp = short_wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.modal-window input[maxlength="24"]')))
                inp.clear()
                inp.send_keys(ANONYMOUS_LOGIN_KEY)
                
                logging.info("Step 4: Submitting Key...")
                submit = driver.find_element(By.XPATH, "//div[.//h2[text()='Restore Account Key']]//button[contains(@class, 'btn-green')]")
                safe_click(driver, submit)
                
                logging.info("Login sequence completed.")
            except Exception as e:
                logging.warning(f"Login click failed ({e}). Attempting Guest fallback...")
                driver.refresh()
                time.sleep(3)
                try:
                    join_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modal-container .btn-green")))
                    safe_click(driver, join_btn)
                except: pass
                play_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
                safe_click(driver, play_btn)

        # 3. Fire and Forget
        logging.info("Step 5: Injecting Movement Script (Blind Injection)...")
        time.sleep(5) # Give the game 5 seconds to process the login
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        
        logging.info("✅ Bot is running. (Monitoring for crashes only)")
        
        # 4. Passive Monitor
        while True:
            time.sleep(20)
            if not driver.service.is_connectable():
                raise RuntimeError("Browser died")
            # We do NOT check for chat/canvas anymore. 
            # If the login sequence finished, we assume we are in.

    except Exception as e:
        logging.error(f"Critical Setup Error: {e}")
        raise

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    
    use_key = True
    
    while True:
        try:
            start_bot(use_key)
        except Exception:
            logging.warning("Bot crash. Restarting in 5s...")
            pass
        finally:
            global driver
            if driver:
                try: driver.quit()
                except: pass
            driver = None
            gc.collect()
            time.sleep(5)

if __name__ == "__main__":
    main()
