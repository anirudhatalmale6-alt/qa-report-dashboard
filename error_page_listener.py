"""
Error Page Listener for WSS Application
----------------------------------------
Detects random 403 and "Apologies" error pages that appear during test execution.
Attaches to a Playwright page and checks after every navigation/response.

Usage:
    from error_page_listener import ErrorPageListener

    # In your test setup (on_start or fixture):
    listener = ErrorPageListener(page, sheet_name="ActiveMember", tracker_path="RunManager.xlsx")

    # Option 1: Auto-detect (listens to every page load automatically)
    listener.start()

    # Option 2: Manual check after specific actions
    listener.check_for_error_page()

    # When done:
    listener.stop()
"""
import logging
import traceback
from datetime import datetime
from typing import Optional, Callable
from playwright.sync_api import Page, Response

logger = logging.getLogger(__name__)


class ApplicationErrorDetected(Exception):
    """Raised when the WSS app shows a 403 or Apologies error page."""
    def __init__(self, error_type: str, message: str, url: str):
        self.error_type = error_type
        self.url = url
        super().__init__(f"{error_type} at {url}: {message}")


class ErrorPageListener:
    """
    Monitors a Playwright page for WSS application error pages (403, Apologies).
    When detected: logs the error, writes to Excel, optionally takes a screenshot,
    and raises ApplicationErrorDetected to stop execution cleanly.
    """

    # Error page signatures - add more patterns as you discover them
    ERROR_SIGNATURES = [
        {
            "name": "403_SESSION_EXPIRED",
            "detect_xpath": "//*[contains(text(),'403 Page') or contains(text(),'OSI 1416')]",
            "message_xpath": "//font[@color='red' or @color='Red']",
            "description": "Session expired / 403 access denied"
        },
        {
            "name": "APOLOGIES_ERROR",
            "detect_xpath": "//*[contains(text(),'Apologies') or contains(text(),'apologies')]",
            "message_xpath": "//*[contains(text(),'Apologies') or contains(text(),'apologies')]",
            "description": "Application apologies/error page"
        },
        {
            "name": "SERVER_ERROR",
            "detect_xpath": "//*[contains(text(),'Internal Server Error') or contains(text(),'500')]",
            "message_xpath": "//body",
            "description": "500 Internal Server Error"
        },
        {
            "name": "VALIDATION_ERROR",
            "detect_xpath": "//*[contains(@class,'Validation Error') or (contains(text(),'Validation Error') and (self::h1 or self::h2 or self::h3 or self::div or self::td or self::th))]",
            "message_xpath": "//ul/li | //ol/li | //*[contains(text(),'You must correct')]",
            "description": "Validation error on form submission"
        },
        {
            "name": "SESSION_TIMEOUT",
            "detect_xpath": "//*[contains(text(),'session has timed out') or contains(text(),'session has expired') or contains(text(),'Session Timeout')]",
            "message_xpath": "//*[contains(text(),'session')]",
            "description": "Session timeout"
        },
        {
            "name": "PAGE_NOT_FOUND",
            "detect_xpath": "//*[contains(text(),'Page Not Found') or contains(text(),'404')]",
            "message_xpath": "//body",
            "description": "404 Page Not Found"
        },
    ]

    def __init__(
        self,
        page: Page,
        sheet_name: str = "",
        data_ref: str = "",
        write_to_cell_fn: Optional[Callable] = None,
        screenshot_dir: str = "error_screenshots",
        on_error: str = "raise",  # "raise" to stop, "log" to just log and continue
    ):
        self.page = page
        self.sheet_name = sheet_name
        self.data_ref = data_ref
        self.write_to_cell_fn = write_to_cell_fn
        self.screenshot_dir = screenshot_dir
        self.on_error = on_error
        self._listening = False
        self._last_check_url = ""
        self._custom_signatures = []

    def add_error_signature(self, name: str, detect_xpath: str, message_xpath: str = "//body", description: str = ""):
        """
        Register a custom error page pattern at runtime.
        Example:
            listener.add_error_signature(
                name="SSN_INVALID",
                detect_xpath="//*[contains(text(),'SSN is not valid')]",
                description="Invalid SSN entered"
            )
        """
        self._custom_signatures.append({
            "name": name,
            "detect_xpath": detect_xpath,
            "message_xpath": message_xpath,
            "description": description or name
        })

    @property
    def all_signatures(self):
        """Combined built-in + custom signatures."""
        return self.ERROR_SIGNATURES + self._custom_signatures

    def start(self):
        """Start auto-listening on every page load."""
        if self._listening:
            return
        self.page.on("load", self._on_page_load)
        self._listening = True
        logger.info("ErrorPageListener started - monitoring for 403/Apologies pages")

    def stop(self):
        """Stop auto-listening."""
        if not self._listening:
            return
        try:
            self.page.remove_listener("load", self._on_page_load)
        except Exception:
            pass
        self._listening = False
        logger.info("ErrorPageListener stopped")

    def _on_page_load(self, page: Page = None):
        """Called automatically on every page load when listening."""
        try:
            self.check_for_error_page()
        except ApplicationErrorDetected:
            raise
        except Exception as e:
            logger.debug(f"Error check failed (non-critical): {e}")

    def check_for_error_page(self) -> Optional[str]:
        """
        Check current page for error signatures.
        Returns None if no error, or raises ApplicationErrorDetected.
        Can also be called manually after any page action.
        """
        current_url = self.page.url

        for sig in self.all_signatures:
            try:
                error_el = self.page.locator(sig["detect_xpath"])
                if error_el.count() > 0:
                    # Error page detected!
                    error_msg = ""
                    try:
                        msg_el = self.page.locator(sig["message_xpath"]).first
                        error_msg = msg_el.text_content(timeout=3000) or ""
                        error_msg = error_msg.strip()[:300]
                    except Exception:
                        error_msg = sig["description"]

                    logger.error(f"ERROR PAGE DETECTED: {sig['name']} at {current_url}")
                    logger.error(f"Message: {error_msg}")

                    # Take screenshot
                    self._save_screenshot(sig["name"])

                    # Write to Excel
                    self._write_error_to_excel(sig["name"], error_msg, current_url)

                    if self.on_error == "raise":
                        raise ApplicationErrorDetected(sig["name"], error_msg, current_url)
                    else:
                        return sig["name"]

            except ApplicationErrorDetected:
                raise
            except Exception:
                continue

        return None

    def _save_screenshot(self, error_type: str):
        """Save a screenshot of the error page."""
        try:
            import os
            os.makedirs(self.screenshot_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.screenshot_dir}/{error_type}_{timestamp}.png"
            self.page.screenshot(path=filename)
            logger.info(f"Error screenshot saved: {filename}")
        except Exception as e:
            logger.warning(f"Could not save screenshot: {e}")

    def _write_error_to_excel(self, error_type: str, message: str, url: str):
        """Write error details to the Excel results."""
        if not self.write_to_cell_fn or not self.data_ref or not self.sheet_name:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.write_to_cell_fn(self.data_ref, "FinalStatus", "Error", self.sheet_name)
            self.write_to_cell_fn(
                self.data_ref, "StackTrace",
                f"{error_type} at {url} [{timestamp}]: {message[:200]}",
                self.sheet_name
            )
            logger.info(f"Error written to Excel: {self.data_ref} in {self.sheet_name}")
        except Exception as e:
            logger.warning(f"Could not write error to Excel: {e}")


# ============================================================
# Helper: Wrap page actions with error checking
# ============================================================
def safe_click(page: Page, locator_str: str, listener: ErrorPageListener, **kwargs):
    """Click an element and check for error page after navigation."""
    page.locator(locator_str).click(**kwargs)
    page.wait_for_load_state("domcontentloaded")
    listener.check_for_error_page()


def safe_goto(page: Page, url: str, listener: ErrorPageListener, **kwargs):
    """Navigate to URL and check for error page."""
    page.goto(url, **kwargs)
    page.wait_for_load_state("domcontentloaded")
    listener.check_for_error_page()
