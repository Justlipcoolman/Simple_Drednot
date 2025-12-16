# drednot_mover.py
# Final Optimization: JS-Loop Driven, No Rejoin Logic, Minimized Overhead.

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

# --- 1. WASM BYPASS (Must run before page load) ---
# Tricks the game engine into accepting our synthetic keystrokes.
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

# --- 2. MOVEMENT LOOP (Injected once) ---
# Runs entirely inside Chrome. Python does nothing but watch.
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

// Clear any existing intervals to prevent duplicates if re-injected
if (window.botInterval) clearInterval(window.botInterval);

window.botInterval = setInterval(() => {
  if (!toggle) return;

  // Move Left
  press('a', 'keydown');
  setTimeout(() => press('a', 'keyup'), 100);

  // Move Right (offset by 200ms)
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
    
    # Aggressive Resource Saving Flags
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--renderer-process-limit=2")
    chrome_options.add_argument("--js-flags=--expose-gc") # Allow manual GC
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=chrome_options)
    
    # Inject WASM Hook (Pre-load)
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": WASM_HOOK_SCRIPT
    })
    
    return d

# --- FLASK (Keep Alive) ---
flask_app = Flask('')
@flask_app.route('/')
def health_check():
    return "Bot Status: Running (JS Loop Active)"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive_ping():
    url = RENDER_EXTERNAL_URL or f"http://localhost:{os.environ.get('PORT', 8080)}"
    logging.info(f"Keep-alive monitor started. Target: {url}")
    while True:
        time.sleep(600) # 10 minutes
        try:
            requests.get(url, timeout=5)
        except:
            pass

# --- MAIN LOGIC ---
def start_bot(use_key_login):
    global driver
    driver = setup_driver()
    
    try:
        logging.info(f"Navigating to {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        wait = WebDriverWait(driver, 20)
        
        # 1. Accept Invite
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".modal-container .btn-green"))).click()
        
        # 2. Login Logic
        if ANONYMOUS_LOGIN_KEY and use_key_login:
            logging.info("Logging in with Key...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Restore old anonymous key')]"))).click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.modal-window input[maxlength="24"]'))).send_keys(ANONYMOUS_LOGIN_KEY)
            driver.find_element(By.XPATH, "//div[.//h2[text()='Restore Account Key']]//button[contains(@class, 'btn-green')]").click()
            # Wait for chat input (Success) OR Login Failed text
            wait.until(EC.any_of(EC.presence_of_element_located((By.ID, "chat-input")), EC.presence_of_element_located((By.XPATH, "//h2[text()='Login Failed']"))))
            if driver.find_elements(By.XPATH, "//h2[text()='Login Failed']"):
                raise ValueError("Invalid Key")
        else:
            logging.info("Logging in as Guest...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Play Anonymously')]"))).click()

        # 3. Wait for Game Load
        wait.until(EC.presence_of_element_located((By.ID, "chat-input")))
        logging.info("✅ Game Loaded.")

        # 4. Inject The JS Movement Loop
        logging.info("Injecting JS Movement Script...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        
        logging.info("Bot is now running autonomously on the browser thread.")
        logging.info("Python script is sleeping to save CPU.")

        # 5. Passive Monitor Loop
        # Python just sits here. The JS in the browser does all the work.
        while True:
            time.sleep(10)
            # Minimal check to ensure browser didn't crash
            if not driver.service.is_connectable():
                raise RuntimeError("Browser died")
            # We explicitly do NOT check for disconnect popups.
            # If the game disconnects, we stay on the disconnect screen 
            # until Render recycles the instance or the outer loop restarts us.

    except Exception as e:
        logging.error(f"Session Error: {e}")
        raise # Throw to main to restart

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    
    use_key = True
    
    while True:
        try:
            start_bot(use_key)
        except ValueError:
            use_key = False # Retry as guest if key fails
        except Exception:
            pass # Just restart
        finally:
            global driver
            if driver:
                try: driver.quit()
                except: pass
            driver = None
            gc.collect()
            time.sleep(5) # Brief pause before hard restart

if __name__ == "__main__":
    main()
