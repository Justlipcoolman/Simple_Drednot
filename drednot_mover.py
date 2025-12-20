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
SHIP_INVITE_LINK = 'https://drednot.io/invite/-EKifhVqXiiFGvEx9JvGnC9H'
ANONYMOUS_LOGIN_KEY = '_M85tFxFxIRDax_nh-HYm1gT'
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- WASM HOOK (NO CLOSURE LEAK) ---
WASM_HOOK_SCRIPT = """
(function() {
    'use strict';

    const win = window;
    const originalInstantiate = win.WebAssembly.instantiate;
    const originalInstantiateStreaming = win.WebAssembly.instantiateStreaming;

    const forceTrue = () => 1;

    function patchImports(importObject) {
        if (!importObject || !importObject.wbg) return;
        for (const key in importObject.wbg) {
            if (key.includes('isTrusted')) {
                importObject.wbg[key] = forceTrue;
            }
        }
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

# --- MOVEMENT SCRIPT (SINGLE TIMER, STABLE) ---
JS_MOVEMENT_SCRIPT = """
console.log("[Bot] Stable movement loop started");

function press(key, type) {
    const kCode = key === 'a' ? 65 : 68;
    const ev = new KeyboardEvent(type, {
        key,
        code: 'Key' + key.toUpperCase(),
        keyCode: kCode,
        which: kCode,
        bubbles: true,
        cancelable: true
    });
    document.dispatchEvent(ev);
}

if (window.botInterval) clearInterval(window.botInterval);

let state = 0;
window.botInterval = setInterval(() => {
    const key = (state++ & 1) === 0 ? 'a' : 'd';
    press(key, 'keydown');
    setTimeout(() => press(key, 'keyup'), 80);
}, 380);
"""

# --- DRIVER SETUP (MEMORY-STABLE) ---
def setup_driver():
    logging.info("🚀 Launching Chromium")

    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--mute-audio")

    # prevent throttling
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")

    # real memory savings
    chrome_options.add_argument("--disable-breakpad")
    chrome_options.add_argument("--disable-crash-reporter")
    chrome_options.add_argument("--disable-features=AudioServiceOutOfProcess")
    chrome_options.add_argument("--memory-pressure-off")

    # JS heap limit ONLY (no expose-gc)
    chrome_options.add_argument("--js-flags=--max-old-space-size=512")

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "disk-cache-size": 0
    }
    chrome_options.add_experimental_option("prefs", prefs)

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # inject WASM hook early
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": WASM_HOOK_SCRIPT}
    )

    # disable devtools buffers (major leak source)
    driver.execute_cdp_cmd("Log.disable", {})
    driver.execute_cdp_cmd("Runtime.disable", {})
    driver.execute_cdp_cmd("Network.enable", {"maxTotalBufferSize": 1024 * 1024})
    driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})

    return driver

# --- BOT CORE ---
def start_bot():
    driver = setup_driver()
    wait = WebDriverWait(driver, 45)

    try:
        logging.info(f"📍 Navigating to invite")
        driver.get(SHIP_INVITE_LINK)

        accept_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class, 'btn-green') and text()='Accept']")
        ))
        driver.execute_script("arguments[0].click();", accept_btn)
        time.sleep(5)

        if ANONYMOUS_LOGIN_KEY:
            try:
                logging.info("🔑 Restoring anonymous key")
                restore_link = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(), 'Restore old anonymous key')]")
                ))
                driver.execute_script("arguments[0].click();", restore_link)

                key_input = wait.until(EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "div.modal-window input")
                ))
                key_input.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));",
                    key_input
                )

                submit_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class,'modal-window')]//button[text()='Submit']")
                ))
                driver.execute_script("arguments[0].click();", submit_btn)
                time.sleep(5)
            except Exception as e:
                logging.warning(f"Key restore skipped: {e}")

        try:
            guest_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Play Anonymously')]")
            ))
            driver.execute_script("arguments[0].click();", guest_btn)
        except:
            pass

        logging.info("⌨️ Injecting movement")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        logging.info("✅ Bot active")

        # ---- STABLE LONG-RUN LOOP (NO CLEANUP, NO RESTART) ----
        while True:
            time.sleep(60)
            _ = driver.title
            logging.info("💓 Heartbeat: Alive")

    except Exception as e:
        logging.error(f"❌ Crash: {e}")
        raise
    finally:
        driver.quit()

# --- FLASK KEEPALIVE ---
flask_app = Flask('')
@flask_app.route('/')
def health():
    return "Bot Running"

def main():
    threading.Thread(
        target=lambda: flask_app.run(
            host='0.0.0.0',
            port=int(os.environ.get("PORT", 10000)),
            use_reloader=False
        ),
        daemon=True
    ).start()

    while True:
        try:
            start_bot()
        except Exception:
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
