# drednot_mover.py
# OPTIMIZED: Infinite Run, V8 Memory Cap, aggressive DOM Cleaning.

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

# --- LOGGING ---
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
        const originalInstantiateStreaming = win.WebAssembly.instantiateStreaming;
        win.WebAssembly.instantiateStreaming = function(source, importObject) {
            if (importObject) patchImports(importObject);
            return originalInstantiateStreaming.apply(this, arguments);
        };
    } catch (e) {}
})();
"""

# --- 2. MEMORY SAVER / NO-RENDER SCRIPT ---
# 1. Forces Canvas to 1x1 pixel.
# 2. Deletes chat logs and UI elements every 5 seconds so text doesn't fill RAM.
DISABLE_RENDERING_SCRIPT = """
console.log("[Bot] Optimization Loop Running...");

function optimizePage() {
    // 1. Cripple Canvas (Stop GPU/CPU rendering)
    const canvas = document.querySelector('canvas');
    if (canvas) {
        if (canvas.width !== 1) canvas.width = 1;
        if (canvas.height !== 1) canvas.height = 1;
        canvas.style.display = 'none'; // Hide completely
    }
    
    // 2. DOM Cleaner (Remove heavy elements)
    // Remove chat content so logs don't fill memory
    const chat = document.getElementById('chat-content');
    if (chat) chat.innerHTML = ''; 

    // Remove backgrounds, stars, particles
    const garbage = document.querySelectorAll('.background, .stars, .particle, .toast-container, iframe, .ad-container');
    garbage.forEach(e => e.remove());
}

// Run immediately and repeatedly
optimizePage();
if (!window.optInterval) {
    window.optInterval = setInterval(optimizePage, 5000);
}
"""

# --- 3. MOVEMENT SCRIPT ---
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

# --- GLOBAL VAR ---
driver = None

# --- BROWSER SETUP ---
def setup_driver():
    logging.info("Launching Optimized Browser...")
    try:
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium"
        
        # --- HEADLESS & RESOLUTION ---
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=800,600")
        
        # --- CRITICAL MEMORY FLAGS ---
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # Force JS Garbage Collection if heap > 128MB
        chrome_options.add_argument("--js-flags=--max_old_space_size=128 --expose-gc")
        # Disable various caches
        chrome_options.add_argument("--disk-cache-size=1")
        chrome_options.add_argument("--disable-application-cache")
        
        # --- DISABLE RENDERING PIPELINE ---
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-gl-drawing-for-tests")
        chrome_options.add_argument("--mute-audio")
        
        # Disable internal features
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-site-isolation-trials") 
        chrome_options.add_argument("--renderer-process-limit=2") 
        
        # Block all visual content
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.default_content_setting_values.notifications": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(executable_path="/usr/bin/chromedriver")
        d = webdriver.Chrome(service=service, options=chrome_options)
        
        d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": WASM_HOOK_SCRIPT
        })
        return d
    except Exception as e:
        logging.error("FAILED TO START BROWSER:")
        logging.error(traceback.format_exc())
        raise e

# --- FLASK ---
flask_app = Flask('')
@flask_app.route('/')
def health_check():
    return "Bot Running (Infinite Mode)"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    url = RENDER_EXTERNAL_URL or f"http://localhost:{os.environ.get('PORT', 8080)}"
    logging.info(f"Monitor: {url}")
    while True:
        time.sleep(60) # Ping every 1 minute
        try: requests.get(url, timeout=5)
        except: pass

def safe_click(d, element):
    try:
        d.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        element.click()
    except Exception:
        d.execute_script("arguments[0].click();", element)

def start_bot(use_key):
    global driver
    driver = setup_driver()
    wait = WebDriverWait(driver, 40)
    
    try:
        logging.info(f"Navigating: {SHIP_INVITE_LINK}")
        driver.get(SHIP_INVITE_LINK)
        
        # Initial cleanup
        try:
            driver.execute_script("document.querySelectorAll('iframe, .ad-container').forEach(e => e.remove());")
        except: pass

        logging.info("Accepting Invite...")
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")))
        safe_click(driver, accept_btn)
        
        time.sleep(3) 
        
        logged_in = False
        if use_key and ANONYMOUS_LOGIN_KEY:
            try:
                logging.info("Attempting Key Login...")
                restore_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Restore old anonymous key')]")))
                safe_click(driver, restore_link)
                
                logging.info("Entering Key...")
                inp = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.modal-window input[maxlength="24"]')))
                inp.click()
                inp.clear()
                inp.send_keys(ANONYMOUS_LOGIN_KEY)
                
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
                time.sleep(1)

                submit_xpath = "//div[contains(@class,'modal-window')]//button[contains(@class, 'btn-green') and text()='Submit']"
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, submit_xpath)))
                safe_click(driver, submit_btn)
                
                logging.info("Key submitted.")
                logged_in = True
            except Exception as e:
                logging.warning(f"Login Failed ({e}). Guest Mode.")
                driver.refresh()
                time.sleep(3)
                try:
                    accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")))
                    safe_click(driver, accept_btn)
                except: pass
        
        if not logged_in:
            logging.info("Playing as Guest...")
            guest_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Anonymously')]")))
            safe_click(driver, guest_btn)
            
        logging.info("Injecting Movement + Memory Scripts...")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        time.sleep(2)
        
        # Inject the heavy memory saver (clears DOM, resizes canvas)
        driver.execute_script(DISABLE_RENDERING_SCRIPT)
        
        logging.info("✅ Bot Active (Infinite Run).")
        
        # Infinite Loop
        while True:
            time.sleep(30)
            if not driver.service.is_connectable():
                raise RuntimeError("Browser disconnected")

    except Exception as e:
        logging.error(f"Error: {e}")
        raise

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    global driver
    driver = None
    
    while True:
        try:
            start_bot(use_key=True)
        except Exception:
            logging.error("Restarting...")
            time.sleep(2)
        finally:
            if driver:
                try: driver.quit()
                except: pass
            driver = None
            gc.collect()
            time.sleep(5)

if __name__ == "__main__":
    main()
