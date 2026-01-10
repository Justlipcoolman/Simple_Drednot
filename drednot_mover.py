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

# --- CONFIG ---
TARGET_URL = 'https://drednot.io/'
ANONYMOUS_LOGIN_KEY = '_M85tFxFxIRDax_nh-HYm1gT'

# --- WASM HOOK ---
WASM_HOOK_SCRIPT = """
(function() {
    'use strict';
    if (window.__wasmHookInstalled) return;
    window.__wasmHookInstalled = true;
    const win = window;
    const origInst = win.WebAssembly.instantiate;
    const origStream = win.WebAssembly.instantiateStreaming;
    const forceTrue = () => 1;
    function patch(imports) {
        try {
            if (!imports || !imports.wbg) return;
            for (const k in imports.wbg) {
                if (k.indexOf('isTrusted') !== -1) imports.wbg[k] = forceTrue;
            }
        } catch (e) {}
    }
    win.WebAssembly.instantiate = function(buf, imports) { patch(imports); return origInst.apply(this, arguments); };
    win.WebAssembly.instantiateStreaming = function(src, imports) { patch(imports); return origStream.apply(this, arguments); };
})();
"""

def setup_driver():
    logging.info("🚀 Launching Chromium")
    opts = Options()
    opts.binary_location = "/usr/bin/chromium"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--mute-audio")
    opts.add_argument("--window-size=1280,720")
    opts.add_argument("--js-flags=--max-old-space-size=512")

    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WASM_HOOK_SCRIPT})
    return driver

def start_bot():
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)

    try:
        logging.info(f"📍 Loading {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(5)

        while True:
            # --- STEP 1: LOGIN CHECK ---
            menu_check = driver.find_elements(By.XPATH, "//button[contains(.,'New Ship')]")
            
            if not menu_check:
                logging.info("🔑 Login required. Restoring key...")
                try:
                    restore = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Restore')]")))
                    driver.execute_script("arguments[0].click();", restore)
                    
                    key_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-window input")))
                    key_input.send_keys(ANONYMOUS_LOGIN_KEY)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input',{bubbles:true}));", key_input)
                    
                    submit = driver.find_element(By.XPATH, "//button[text()='Submit']")
                    driver.execute_script("arguments[0].click();", submit)
                    time.sleep(2)
                    
                    play = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Play Anonymously')]")))
                    driver.execute_script("arguments[0].click();", play)
                    time.sleep(3)
                except Exception as e:
                    logging.warning(f"Login flow issue (maybe already in?): {e}")

            # --- STEP 2: CREATE SHIP ---
            try:
                logging.info("🚢 Creating ship...")
                btn_new = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'New Ship')]")))
                driver.execute_script("arguments[0].click();", btn_new)
                time.sleep(1)

                btn_launch = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Launch')]")))
                driver.execute_script("arguments[0].click();", btn_launch)
                logging.info("🚀 Ship Launched!")
                
                # Stay in ship for a few seconds
                time.sleep(8) 

                # --- STEP 3: EXIT (NO ESC KEY) ---
                logging.info("🚪 Attempting to Exit Ship (JS Click)...")
                # Using JS to click even if the button is hidden by the game canvas
                driver.execute_script("""
                    const btn = document.querySelector('#exit_button') || 
                                [...document.querySelectorAll('button')].find(b => b.textContent.includes('Exit'));
                    if (btn) btn.click();
                """)
                
                logging.info("✅ Exit command sent.")
                time.sleep(4) # Wait to return to menu

            except Exception as e:
                logging.warning(f"Loop interrupted: {e}. Refreshing...")
                driver.refresh()
                time.sleep(5)

    except Exception as e:
        logging.error(f"🔥 Critical Crash: {e}")
        raise
    finally:
        driver.quit()

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route("/")
def health(): return "Bot Running"

def main():
    # Start Flask in background
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000, use_reloader=False), daemon=True).start()
    
    # Run Bot
    while True:
        try:
            start_bot()
        except Exception:
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
