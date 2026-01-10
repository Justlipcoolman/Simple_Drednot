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

# --- WASM HOOK (Essential for Drednot Engine) ---
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

# --- YOUR SHIP-MAKING LOOP ---
JS_SHIP_LOOP = """
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

  console.log("[Bot] Ship-creation loop started");

  while (true) {
    try {
        // 1. Create New Ship
        console.log("Cycle: Creating New Ship...");
        clickByText("button", "New Ship");
        await sleep(2000);

        // 2. Launch the Ship
        console.log("Cycle: Launching...");
        clickByText("button", "Launch");
        await sleep(4000); // Give time for the game to load/spawn

        // 3. Exit immediately (leaving the ship)
        console.log("Cycle: Exiting ship...");
        const exitBtn = document.querySelector("#exit_button");
        if (exitBtn) {
            exitBtn.click();
        } else {
            // Fallback if #exit_button isn't found
            clickByText("button", "Exit"); 
        }
        
        await sleep(3000); // Wait for return to main menu
    } catch (e) {
        console.error("Loop error:", e);
        await sleep(2000);
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
    wait = WebDriverWait(driver, 35)

    try:
        logging.info(f"📍 Navigating to {TARGET_URL}")
        driver.get(TARGET_URL)

        # Handle Anonymous Key Restore
        if ANONYMOUS_LOGIN_KEY:
            try:
                restore_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(),'Restore old anonymous key')]")
                ))
                driver.execute_script("arguments[0].click();", restore_btn)

                key_input = wait.until(EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "div.modal-window input")
                ))
                key_input.send_keys(ANONYMOUS_LOGIN_KEY)
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));", key_input
                )

                submit = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Submit']")))
                driver.execute_script("arguments[0].click();", submit)
                time.sleep(3)
                logging.info("🔑 Key restored successfully")
            except Exception as e:
                logging.warning(f"Key restore step skipped: {e}")

        # Click Play to enter the menu
        try:
            play = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(.,'Play Anonymously')]")
            ))
            driver.execute_script("arguments[0].click();", play)
            time.sleep(5)
        except:
            pass

        logging.info("⚙️ Injecting Ship Creation Loop")
        driver.execute_script(JS_SHIP_LOOP)
        logging.info("✅ Bot active: Making ships and exiting.")

        while True:
            time.sleep(60)
            _ = driver.title # Heartbeat check
            logging.info("💓 Heartbeat: Bot is still running")

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
            logging.info("Restarting in 10s...")
            time.sleep(10)
            gc.collect()

if __name__ == "__main__":
    main()
