# drednot_mover.py
# VERSION: Infinite Uptime, Aggressive Memory Management, No Restarts

import os
import time
import logging
import threading
import gc
import requests
import traceback
import resource
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

# --- MEMORY PROTECTION ---
def set_soft_memory_limit():
    """Tells the OS to warn/throw errors before the container crashes hard."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        # Set limit to 80% of typical 512MB container to allow Python to catch the error
        resource.setrlimit(resource.RLIMIT_AS, (450 * 1024 * 1024, hard)) 
    except:
        pass

# --- 1. PERFORMANCE KILLER SCRIPT ---
# This disables rendering and throttles the engine to 1 FPS
JS_OPTIMIZATION = """
(function() {
    console.log("⚡ INJECTING OPTIMIZATIONS ⚡");
    
    // 1. Disable Console Logs (Prevents log buildup in RAM)
    console.log = function() {};
    console.info = function() {};
    console.warn = function() {};
    
    // 2. Throttle Animation Frame (Game Logic runs, Graphics stop)
    // This forces the game loop to run only once per second (1 FPS)
    const originalRAF = window.requestAnimationFrame;
    window.requestAnimationFrame = function(callback) {
        window.setTimeout(() => {
            callback(Date.now());
        }, 1000); // 1000ms delay = 1 FPS
    };

    // 3. WebAssembly Hook (Keep existing logic)
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

# --- 2. MOVEMENT SCRIPT ---
JS_MOVEMENT = """
// Simple movement ticker
if (window.botInterval) clearInterval(window.botInterval);
window.botInterval = setInterval(() => {
    // Press A
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'a', code: 'KeyA', bubbles:true}));
    window.dispatchEvent(new KeyboardEvent('keydown', {key: 'a', code: 'KeyA', bubbles:true}));
    setTimeout(() => {
        document.dispatchEvent(new KeyboardEvent('keyup', {key: 'a', code: 'KeyA', bubbles:true}));
        window.dispatchEvent(new KeyboardEvent('keyup', {key: 'a', code: 'KeyA', bubbles:true}));
    }, 100);

    // Press D
    setTimeout(() => {
        document.dispatchEvent(new KeyboardEvent('keydown', {key: 'd', code: 'KeyD', bubbles:true}));
        window.dispatchEvent(new KeyboardEvent('keydown', {key: 'd', code: 'KeyD', bubbles:true}));
        setTimeout(() => {
            document.dispatchEvent(new KeyboardEvent('keyup', {key: 'd', code: 'KeyD', bubbles:true}));
            window.dispatchEvent(new KeyboardEvent('keyup', {key: 'd', code: 'KeyD', bubbles:true}));
        }, 100);
    }, 200);
}, 400);
"""

# --- FLASK ---
flask_app = Flask('')
@flask_app.route('/')
def health_check(): return "Bot Alive"
def run_flask(): flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- KEEP ALIVE ---
def keep_alive():
    url = RENDER_EXTERNAL_URL or f"http://localhost:{os.environ.get('PORT', 8080)}"
    while True:
        time.sleep(60)
        try: requests.get(url, timeout=5)
        except: pass

# --- BROWSER SETUP ---
def setup_driver():
    logging.info("🚀 Launching Chrome...")
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    
    # Core Headless
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=600,400") # Small window saves buffer RAM
    
    # Aggressive Memory Saving
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer") # Disable CPU rendering
    options.add_argument("--disable-extensions")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-application-cache")
    
    # V8 Optimization (Limit JS RAM)
    options.add_argument("--js-flags=--max_old_space_size=256")
    
    # Process management
    options.add_argument("--renderer-process-limit=1")
    options.add_argument("--disable-site-isolation-trials")
    
    service = Service(executable_path="/usr/bin/chromedriver")
    d = webdriver.Chrome(service=service, options=options)
    
    # Inject Optimization immediately on load
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": JS_OPTIMIZATION})
    return d

def perform_maintenance(d):
    """Cleans memory without closing the browser"""
    try:
        # 1. Clear Network Cache (CDP)
        d.execute_cdp_cmd("Network.clearBrowserCache", {})
        
        # 2. Force Garbage Collection (CDP) - This is the magic command
        d.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
        
        # 3. Clear Local Console
        d.execute_script("console.clear();")
    except Exception as e:
        logging.warning(f"Maintenance warning: {e}")

def safe_click(d, element):
    try:
        d.execute_script("arguments[0].click();", element)
    except:
        element.click()

def start_bot():
    global driver
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

    try:
        logging.info("🌍 Navigating...")
        driver.get(SHIP_INVITE_LINK)
        
        # Remove Heavy Elements immediately
        driver.execute_script("document.body.style.backgroundColor = 'black';")
        
        logging.info("👉 Clicking Accept...")
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Accept')]")))
        safe_click(driver, accept_btn)
        time.sleep(2)

        # Login Logic
        logged_in = False
        if ANONYMOUS_LOGIN_KEY:
            try:
                logging.info("🔑 Logging in...")
                wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Restore')]"))).click()
                inp = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[maxlength="24"]')))
                inp.clear()
                inp.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", inp)
                time.sleep(1)
                safe_click(driver, wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Submit')]"))))
                logged_in = True
            except:
                logging.warning("Login failed, falling back to Guest.")
                driver.refresh()
                time.sleep(2)
                try: safe_click(driver, wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Accept')]"))))
                except: pass

        if not logged_in:
            safe_click(driver, wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Play Anonymously')]"))))

        logging.info("✅ Game Loaded. Injecting Movement.")
        driver.execute_script(JS_MOVEMENT)
        
        # FINAL OPTIMIZATION: Delete the Canvas
        # This stops the browser from painting pixels but keeps WASM running
        time.sleep(5)
        logging.info("✂️ Removing Canvas to save RAM...")
        driver.execute_script("""
            const canvas = document.getElementById('canvas');
            if(canvas) { canvas.remove(); }
            const ui = document.getElementById('ui-container');
            if(ui) { ui.style.display = 'none'; }
        """)

        # --- INFINITE LOOP ---
        logging.info("♾️ Bot is running indefinitely.")
        maintenance_counter = 0
        
        while True:
            time.sleep(10)
            
            if not driver.service.is_connectable():
                raise RuntimeError("Browser crashed")
            
            # Every 60 seconds (10s * 6), clean memory
            maintenance_counter += 1
            if maintenance_counter >= 6:
                perform_maintenance(driver)
                maintenance_counter = 0
                # Re-inject movement just in case
                driver.execute_script(JS_MOVEMENT) 

    except Exception as e:
        logging.error(f"FATAL ERROR: {e}")
        raise

def main():
    set_soft_memory_limit()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    global driver
    while True:
        try:
            start_bot()
        except Exception:
            logging.info("⚠️ Bot crash detected. Respawning in 5s...")
            try: driver.quit()
            except: pass
            time.sleep(5)

if __name__ == "__main__":
    main()
