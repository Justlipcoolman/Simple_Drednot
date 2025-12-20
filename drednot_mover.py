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

# --- WASM HOOK (SAFE VERSION) ---
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
                if (k.indexOf('isTrusted') !== -1) {
                    imports.wbg[k] = forceTrue;
                }
            }
        } catch (e) {}
    }

    win.WebAssembly.instantiate = function(buf, imports) {
        patch(imports);
        return origInst.apply(this, arguments);
    };

    win.WebAssembly.instantiateStreaming = function(src, imports) {
        patch(imports);
        return origStream.apply(this, arguments);
    };
})();
"""

# --- MOVEMENT SCRIPT (STABLE) ---
JS_MOVEMENT_SCRIPT = """
console.log("[Bot] Movement loop started");

function press(key, type) {
    const k = key === 'a' ? 65 : 68;
    document.dispatchEvent(new KeyboardEvent(type, {
        key,
        code: 'Key' + key.toUpperCase(),
        keyCode: k,
        which: k,
        bubbles: true
    }));
}

if (window.botInterval) clearInterval(window.botInterval);

let s = 0;
window.botInterval = setInterval(() => {
    const key = (s++ & 1) ? 'd' : 'a';
    press(key, 'keydown');
    setTimeout(() => press(key, 'keyup'), 80);
}, 400);
"""

# --- DRIVER SETUP (CRASH-SAFE) ---
def setup_driver():
    logging.info("🚀 Launching Chromium")

    opts = Options()
    opts.binary_location = "/usr/bin/chromium"

    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--mute-audio")

    # prevent throttling
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")

    # crash hardening (IMPORTANT)
    opts.add_argument("--disable-breakpad")
    opts.add_argument("--disable-crash-reporter")
    opts.add_argument("--disable-features=AudioServiceOutOfProcess")
    opts.add_argument("--disable-features=CalculateNativeWinOcclusion")

    # JS heap limit ONLY
    opts.add_argument("--js-flags=--max-old-space-size=512")

    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "disk-cache-size": 0
    })

    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"),
        options=opts
    )

    # Inject WASM hook early
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": WASM_HOOK_SCRIPT}
    )

    return driver

# --- BOT CORE ---
def start_bot():
    driver = setup_driver()
    wait = WebDriverWait(driver, 45)

    try:
        logging.info("📍 Navigating to invite")
        driver.get(SHIP_INVITE_LINK)

        # AFTER page load → disable devtools buffers (safe timing)
        driver.execute_cdp_cmd("Log.disable", {})
        driver.execute_cdp_cmd("Runtime.disable", {})
        driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})

        accept = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class,'btn-green') and text()='Accept']")
        ))
        driver.execute_script("arguments[0].click();", accept)
        time.sleep(5)

        if ANONYMOUS_LOGIN_KEY:
            try:
                restore = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(),'Restore old anonymous key')]")
                ))
                driver.execute_script("arguments[0].click();", restore)

                key_input = wait.until(EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "div.modal-window input")
                ))
                key_input.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));",
                    key_input
                )

                submit = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[text()='Submit']")
                ))
                driver.execute_script("arguments[0].click();", submit)
                time.sleep(5)
            except Exception as e:
                logging.warning(f"Key restore skipped: {e}")

        try:
            play = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(.,'Play Anonymously')]")
            ))
            driver.execute_script("arguments[0].click();", play)
        except:
            pass

        logging.info("⌨️ Injecting movement")
        driver.execute_script(JS_MOVEMENT_SCRIPT)
        logging.info("✅ Bot active")

        # STABLE LOOP
        while True:
            time.sleep(60)
            _ = driver.title
            logging.info("💓 Heartbeat")

    except Exception as e:
        logging.error(f"❌ Crash: {e}")
        raise
    finally:
        driver.quit()

# --- FLASK ---
app = Flask(__name__)
@app.route("/")
def health():
    return "Bot Running"

def main():
    threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
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
