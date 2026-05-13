import os
import asyncio
from langchain_core.tools import tool
from playwright.async_api import async_playwright
from fpdf import FPDF

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

@dataclass
class BrowserSession:
    playwright: Any = None
    browser: Any = None
    page: Any = None
    artifact_dir: str = ""
    report_path: str = ""

_browser_session: ContextVar[BrowserSession] = ContextVar("browser_session")

def get_session() -> BrowserSession:
    try:
        return _browser_session.get()
    except LookupError:
        # Fallback for outside-context runs if any, though shouldn't happen
        session = BrowserSession()
        _browser_session.set(session)
        return session

def set_artifact_context(artifact_dir: str, report_path: str):
    """Sets the active run artifact paths for screenshots and reports."""
    session = get_session()
    session.artifact_dir = artifact_dir
    session.report_path = report_path
    os.makedirs(artifact_dir, exist_ok=True)

async def start_browser():
    """Initializes the persistent browser session asynchronously for current context."""
    session = get_session()
    if not session.playwright:
        session.playwright = await async_playwright().start()
        headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        slow_mo = int(os.getenv("BROWSER_SLOW_MO_MS", "300"))
        session.browser = await session.playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        session.page = await session.browser.new_page()
        session.page.set_default_timeout(int(os.getenv("BROWSER_ACTION_TIMEOUT_MS", "15000")))
        session.page.set_default_navigation_timeout(int(os.getenv("BROWSER_NAVIGATION_TIMEOUT_MS", "60000")))

async def close_browser():
    """Safely closes the browser session asynchronously."""
    session = get_session()
    try:
        if session.page: await session.page.close()
        if session.browser: await session.browser.close()
        if session.playwright: await session.playwright.stop()
    except Exception as e:
        print(f"[Browser] Error during shutdown: {e}")
    finally:
        session.playwright = None
        session.browser = None
        session.page = None

@tool
async def navigate_to_url(url: str) -> str:
    """Navigates to a specified URL and waits for the page to be ready."""
    try:
        print(f"[Browser] Navigating to {url}...")
        # Wait for 'load' instead of just 'domcontentloaded' for better stability
        await get_session().page.goto(url, wait_until="load", timeout=60000)
        
        # Additional wait for network to settle if possible, but don't block forever
        try:
            await get_session().page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        title = await get_session().page.title()
        return f"Successfully navigated to {url}. Page title: {title}"
    except Exception as e:
        return f"Failed to navigate: {repr(e)}"

@tool
async def wait_for_page_ready(timeout_ms: int = 10000) -> str:
    """Waits until the current page has reached a stable DOM state."""
    try:
        await get_session().page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        try:
            await get_session().page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass
        title = await get_session().page.title()
        return f"Page ready enough for testing. Current title: {title}. Current URL: {get_session().page.url}"
    except Exception as e:
        return f"Page readiness wait failed: {repr(e)}"

@tool
async def get_page_state() -> str:
    """Returns the current URL, title, and a compact visible-text snapshot."""
    try:
        title = await get_session().page.title()
        text = await get_session().page.locator("body").inner_text(timeout=5000)
        compact_text = " ".join(text.split())[:2000]
        return f"Current URL: {get_session().page.url}\nPage title: {title}\nVisible text snapshot:\n{compact_text}"
    except Exception as e:
        return f"Failed to get page state: {repr(e)}"

@tool
async def analyze_page_elements() -> str:
    """Extracts visible interactive elements with stable locator hints. 
    Use this to understand what can be clicked or filled on the current view."""
    try:
        print("[Browser] Scanning interactive elements...")
        # Ensure page is stable
        await get_session().page.wait_for_load_state("domcontentloaded", timeout=5000)
        
        elements = await get_session().page.evaluate("""() => {
            const selectors = [
                'input:not([type="hidden"])',
                'textarea',
                'select',
                'button',
                'a',
                '[role="button"]',
                '[role="link"]',
                '[role="checkbox"]',
                '[role="radio"]',
                '[contenteditable="true"]',
                '[onclick]'
            ].join(',');

            const valueOf = (element, name) => element.getAttribute(name) || '';
            const labelFor = (element) => {
                if (element.labels && element.labels.length) {
                    return Array.from(element.labels).map(label => label.innerText.trim()).join(' ');
                }
                const id = element.id;
                if (id) {
                    const label = document.querySelector(`label[for="${id}"]`);
                    if (label) return label.innerText.trim();
                }
                return '';
            };

            return Array.from(document.querySelectorAll(selectors))
                .filter(e => {
                    const rect = e.getBoundingClientRect();
                    const style = window.getComputedStyle(e);
                    return rect.width > 0 && 
                           rect.height > 0 && 
                           style.visibility !== 'hidden' && 
                           style.display !== 'none' &&
                           rect.top < window.innerHeight &&
                           rect.left < window.innerWidth;
                })
                .map(e => {
                    const tag = e.tagName.toLowerCase();
                    const text = (e.innerText || e.value || '').trim().replace(/\\s+/g, ' ').substring(0, 50);
                    const type = e.getAttribute('type') || '';
                    
                    const attributes = {
                        'data-testid': valueOf(e, 'data-testid'),
                        'aria-label': valueOf(e, 'aria-label'),
                        'id': e.id,
                        'name': valueOf(e, 'name'),
                        'placeholder': valueOf(e, 'placeholder'),
                        'label': labelFor(e),
                        'role': valueOf(e, 'role'),
                        'type': type
                    };

                    const attrStr = Object.entries(attributes)
                        .filter(([_, v]) => v)
                        .map(([k, v]) => `${k}="${v}"`)
                        .join(' ');

                    return `<${tag} ${attrStr}>${text}</${tag}>`;
                })
                .slice(0, 50)
                .join('\\n');
        }""")
        
        if not elements:
            return "No interactable elements found in the current viewport. Try scrolling or waiting."
        return f"Visible interactable elements:\n{elements}"
    except Exception as e:
        return f"Failed to analyze page: {repr(e)}"

@tool
async def click_element(selector_or_text: str) -> str:
    """Clicks a button or link based on its text, name, aria-label, data-testid, or CSS selector."""
    try:
        print(f"[Browser] AI clicking on '{selector_or_text}'...")
        
        # Strategic locators in order of reliability
        locators = [
            get_session().page.locator(f"[data-testid='{selector_or_text}']"),
            get_session().page.get_by_role("button", name=selector_or_text, exact=False),
            get_session().page.get_by_role("link", name=selector_or_text, exact=False),
            get_session().page.get_by_label(selector_or_text, exact=False),
            get_session().page.get_by_text(selector_or_text, exact=False),
            get_session().page.locator(selector_or_text)
        ]

        for locator in locators:
            try:
                # Check if locator matches anything before trying to click
                count = await locator.count()
                if count > 0:
                    target = locator.first
                    # Ensure it's in view
                    await target.scroll_into_view_if_needed()
                    # Click with a reasonable timeout
                    await target.click(timeout=5000)
                    
                    # Wait for navigation or potential UI change
                    try:
                        await get_session().page.wait_for_load_state("domcontentloaded", timeout=2000)
                    except:
                        pass
                        
                    return f"Successfully clicked on '{selector_or_text}'"
            except Exception:
                continue

        return f"Failed to click '{selector_or_text}': no visible or clickable element found matching this description."
    except Exception as e:
        return f"Error during click operation: {repr(e)}"

@tool
async def fill_input(selector_or_placeholder: str, text: str) -> str:
    """Fills an input field by label, placeholder, id, name, or CSS selector."""
    try:
        print(f"[Browser] AI typing '{text}' into '{selector_or_placeholder}'...")
        
        locators = [
            get_session().page.locator(f"[data-testid='{selector_or_placeholder}']"),
            get_session().page.get_by_label(selector_or_placeholder, exact=False),
            get_session().page.get_by_placeholder(selector_or_placeholder, exact=False),
            get_session().page.locator(f"[name='{selector_or_placeholder}']"),
            get_session().page.locator(f"#{selector_or_placeholder}"),
            get_session().page.locator(selector_or_placeholder)
        ]

        for locator in locators:
            try:
                if await locator.count() > 0:
                    target = locator.first
                    await target.scroll_into_view_if_needed()
                    # Use fill which is faster than type and handles clearing
                    await target.fill(text, timeout=5000)
                    return f"Successfully filled '{selector_or_placeholder}' with text."
            except Exception:
                continue

        return f"Failed to fill '{selector_or_placeholder}': element not found or not editable."
    except Exception as e:
        return f"Error during fill operation: {repr(e)}"

@tool
async def press_key(key: str) -> str:
    """Presses a keyboard key such as Enter, Tab, Escape, or ArrowDown."""
    try:
        await get_session().page.keyboard.press(key)
        await asyncio.sleep(1)
        return f"Successfully pressed key {key}."
    except Exception as e:
        return f"Failed to press key {key}: {repr(e)}"

@tool
async def assert_text_visible(expected_text: str) -> str:
    """Checks whether expected text is visible on the current page."""
    try:
        locator = get_session().page.get_by_text(expected_text, exact=False).first
        if await locator.count() > 0 and await locator.is_visible(timeout=5000):
            return f"Assertion passed: visible text contains '{expected_text}'."
        return f"Assertion failed: visible text does not contain '{expected_text}'."
    except Exception as e:
        return f"Assertion failed for text '{expected_text}': {repr(e)}"

@tool
async def take_evidence_screenshot(filename: str = "evidence.png") -> str:
    """Takes a screenshot of the current page state."""
    try:
        print("[Browser] Capturing visual evidence...")
        screenshot_path = filename
        if not os.path.isabs(screenshot_path):
            screenshot_path = os.path.join(get_session().artifact_dir, filename)
        await get_session().page.screenshot(path=screenshot_path)
        return f"Screenshot successfully saved to {screenshot_path}"
    except Exception as e:
        return f"Failed to take screenshot: {repr(e)}"

@tool
async def generate_pdf_report(screenshot_path: str, summary: str) -> str:
    """Generates a detailed PDF report. Differentiates between steps, hurdles, and outcome."""
    try:
        if screenshot_path and not os.path.isabs(screenshot_path):
            screenshot_path = os.path.join(get_session().artifact_dir, screenshot_path)

        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, txt="AI QA Agent - Mission Execution Report", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=11)
        safe_summary = summary.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, txt=safe_summary)
        
        if os.path.exists(screenshot_path):
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, txt="Visual Evidence (Final State):", ln=True)
            pdf.ln(5)
            pdf.image(screenshot_path, x=10, y=30, w=190)
            
        os.makedirs(os.path.dirname(get_session().report_path), exist_ok=True)
        pdf.output(get_session().report_path)
        return f"Report successfully generated at {get_session().report_path}."
    except Exception as e:
        return f"Failed to generate report: {repr(e)}"

@tool
async def scroll_page(direction: str = "down") -> str:
    """Scrolls the page 'up' or 'down' to reveal more content."""
    try:
        session = get_session()
        page = session.page
        if direction.lower() == "down":
            await page.evaluate("window.scrollBy(0, window.innerHeight / 2)")
        else:
            await page.evaluate("window.scrollBy(0, -window.innerHeight / 2)")
        await asyncio.sleep(0.5)
        return f"Successfully scrolled {direction}."
    except Exception as e:
        return f"Failed to scroll: {repr(e)}"

@tool
async def pause_for_human(seconds: int = 30) -> str:
    """Pauses the AI to allow the human to manually solve a CAPTCHA or log in."""
    try:
        print(f"\n[Browser] 🛑 AI PAUSED FOR {seconds} SECONDS.")
        print(f"[Browser] 👉 HUMAN: Please handle the login or security check now!")
        
        # Safely handle potential server shutdown during sleep
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            print("\n[Browser] Sleep cancelled due to server shutdown.")
            raise 
            
        print(f"[Browser] ▶️ AI RESUMING...")
        return f"Waited {seconds} seconds. Page state has likely changed. Call analyze_page_elements next."
    except Exception as e:
        if not isinstance(e, asyncio.CancelledError):
             return f"Failed to pause: {repr(e)}"
        raise
