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

# --- SAFE WASM HOOK (NO LEAKS / NO DOUBLE PATCH) ---
WASM_HOOK_SCRIPT = """
(function () {
    'use strict';
    if (window.__wasmHookInstalled) return;
    window.__wasmHookInstalled = true;

    const forceTrue = () => 1;
    const win = window;

    const origInst = win.WebAssembly.instantiate;
    const origStream = win.WebAssembly.instantiateStreaming;

    function patch(imports) {
        try {
            if (!imports || !imports.wbg) return;
            for (const k in imports.wbg) {
                if (k.includes('isTrusted')) {
                    imports.wbg[k] = forceTrue;
                }
            }
        } catch (e) {}
    }

    win.WebAssembly.instantiate = function (buf, imports) {
        patch(imports);
        return origInst.apply(this, arguments);
    };

    win.WebAssembly.instantiateStreaming = function (src, imports) {
        patch(imports);
        return origStream.apply(this, arguments);
    };
})();
"""

# --- STABLE MOVEMENT (SINGLE TIMER) ---
JS_MOVEMENT_SCRIPT = """
console.log('[Bot] Movement started');

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

# --- DRIVER SETUP (HARD MEMORY CAPPED FOR RENDER) ---
def setup_driver():
    logging.info("🚀 Launching Chromium")

    opts = Options()
    opts.binary_location = "/usr/bin/chromium"

    # core
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--mute-audio")

    # process + memory caps (CRITICAL)
    opts.add_argument("--single-process")
    opts.add_argument("--renderer-process-limit=1")
    opts.add_argument("--disable-site-isolation-trials")
    opts.add_argument("--disable-features=SitePerProcess")
    opts.add_argument("--disable-features=SharedArrayBuffer")

    # wasm + js hard limits
    opts.add_argument("--js-flags=--max-old-space-size=256")
    opts.add_argument("--disable-features=WebAssemblyTiering")
    opts.add_argument("--disable-features=WebAssemblyLazyCompilation")

    # gpu / raster kill
    opts.add_argument("--disable-gpu-compositing")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-accelerated-2d-canvas")
    opts.add_argument("--disable-accelerated-video-decode")

    # background / helpers
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-breakpad")
    opts.add_argument("--disable-crash-reporter")
    opts.add_argument("--disable-component-update")
    opts.add_argument("--disable-domain-reliability")
    opts.add_argument("--disable-client-side-phishing-detection")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-sync")
    opts.add_argument("--disable-translate")
    opts.add_argument("--disable-features=AudioServiceOutOfProcess")
    opts.add_argument("--disable-features=CalculateNativeWinOcclusion")

    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "disk-cache-size": 0
    })

    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"),
        options=opts
    )

    # inject WASM hook before page scripts
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

        # disable devtools buffers AFTER load (safe)
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

        # ---- LONG-RUN LOOP ----
        while True:
            time.sleep(60)
            _ = driver.title
            logging.info("💓 Heartbeat")

    except Exception as e:
        logging.error(f"❌ Crash: {e}")
        raise
    finally:
        driver.quit()

# --- FLASK KEEPALIVE ---
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
