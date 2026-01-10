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

# --- WASM HOOK (Necessary for Drednot's engine) ---
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

# --- YOUR CUSTOM LOOP SCRIPT ---
JS_LOOP_SCRIPT = """
(async function () {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function clickByText(tag, text) {
    const el = [...document.querySelectorAll(tag)]
      .find(e => e.textContent.trim().includes(text));
    if (el) {
        el.click();
        return true;
    }
    return false;
  }

  console.log("[Bot] Cycle Script Started");

  while (true) {
    try {
        console.log("New cycle: Clicking New Ship");
        clickByText("button", "New Ship");
        await sleep(2000);

        console.log("Cycle: Clicking Launch");
        clickByText("button", "Launch");
        await sleep(4000);

        console.log("Cycle: Clicking Exit");
        const exitBtn = document.querySelector("#exit_button");
        if (exitBtn) exitBtn.click();
        
        await sleep(2000);
    } catch (e) {
        console.error("Loop error:", e);
        await sleep(1000);
    }
  }
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
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--js-flags=--max-old-space-size=512")

    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "disk-cache-size": 0
    })

    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"),
        options=opts
    )

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": WASM_HOOK_SCRIPT}
    )
    return driver

def start_bot():
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

    try:
        logging.info(f"📍 Navigating to {TARGET_URL}")
        driver.get(TARGET_URL)

        # 1. Handle Anonymous Login Key
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
                time.sleep(3)
                logging.info("🔑 Login key restored")
            except Exception as e:
                logging.warning(f"Key restore skipped or failed: {e}")

        # 2. Enter the Game Menu
        try:
            play = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(.,'Play Anonymously')]")
            ))
            driver.execute_script("arguments[0].click();", play)
            logging.info("🖱️ Clicked Play")
        except:
            logging.info("Play button not found, might already be in menu")

        # 3. Inject the user's custom loop
        time.sleep(5) # Wait for menu to stabilize
        logging.info("⚙️ Injecting Custom Loop Script")
        driver.execute_script(JS_LOOP_SCRIPT)
        
        logging.info("✅ Bot loop active")

        # Keep Python alive while the JS runs in the browser
        while True:
            time.sleep(60)
            _ = driver.title # Check if driver is still alive
            logging.info("💓 Heartbeat: Bot script is running")

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
            logging.info("Restarting bot in 10 seconds...")
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
