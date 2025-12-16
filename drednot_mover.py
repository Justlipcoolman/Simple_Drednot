# drednot_mover.py
# Final Fix: Ad-Blocker, Force-Click, JS-Loop Driven.

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
    
    # Flags
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080") # FIX: Prevent elements overlapping
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
    return "Bot Status: Running (JS Loop Active)"

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

# --- MAIN LOGIC ---
def start_bot(use_key_login):
    global driver
    driver = setup_driver()
    
    try:
        logging.info(f"Navigating to {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        wait = WebDriverWait(driver, 20)
        
        # --- FIX: REMOVE ADS ---
        try:
            driver.execute_script("""
                const ads = document.querySelectorAll('a[href*="advertising"], .ad-container, iframe');
                ads.forEach(el => el.remove());
            """)
        except: pass

        # 1. Accept Invite (FORCE CLICK)
        join_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".modal-container .btn-green")))
        # Use JS click to bypass "Element Click Intercepted"
        driver.execute_script("arguments[0].click();", join_btn)
        
        # 2. Login Logic
        if ANONYMOUS_LOGIN_KEY and use_key_login:
            logging.info("Logging in with Key...")
            link = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Restore old anonymous key')]")))
            driver.execute_script("arguments[0].click();", link) # Force click link
            
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.modal-window input[maxlength="24"]'))).send_keys(ANONYMOUS_LOGIN_KEY)
            
            submit = driver.find_element(By.XPATH, "//div[.//h2[text()='Restore Account Key']]//button[contains(@class, 'btn-green')]")
            driver.execute_script("arguments[0].click();", submit) # Force click submit

            wait.until(EC.any_of(EC.presence_of_element_located((By.ID, "chat-input")), EC.presence_of_element_located((By.XPATH, "//h2[text()='Login Failed']"))))
            if driver.find_elements(By.XPATH, "//h2[text()='Login Failed']"):
                raise ValueError("Invalid Key")
        else:
            logging.info("Logging in as Guest...")
            play_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
            driver.execute_script("arguments[0].click();", play_btn) # Force click play

        # 3. Wait for Game Load
        wait.until(EC.presence_of_element_located((By.ID, "chat-input")))
        logging.info("✅ Game Loaded.")

        # 4. Inject Movement
        logging.info("Injecting JS Movement Script...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        
        logging.info("Bot active. Python sleeping.")
        
        while True:
            time.sleep(10)
            if not driver.service.is_connectable():
                raise RuntimeError("Browser died")

    except Exception as e:
        logging.error(f"Session Error: {e}")
        raise

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    
    use_key = True
    
    while True:
        try:
            start_bot(use_key)
        except ValueError:
            use_key = False
        except Exception:
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
