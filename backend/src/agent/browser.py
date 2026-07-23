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
    memory_enabled: bool = True

_active_execution_id: ContextVar[str] = ContextVar("active_execution_id", default="default_execution")
_browser_sessions: dict[str, BrowserSession] = {}
active_pauses: dict[str, asyncio.Event] = {}

def get_session() -> BrowserSession:
    try:
        exec_id = _active_execution_id.get()
    except LookupError:
        exec_id = "default_execution"
    if exec_id not in _browser_sessions:
        _browser_sessions[exec_id] = BrowserSession()
    return _browser_sessions[exec_id]

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

async def close_browser_session(exec_id: str):
    """Closes browser session context for a specific execution ID."""
    if exec_id in _browser_sessions:
        session = _browser_sessions[exec_id]
        try:
            if session.page: await session.page.close()
            if session.browser: await session.browser.close()
            if session.playwright: await session.playwright.stop()
        except Exception as e:
            print(f"[Browser] Error during session {exec_id} shutdown: {e}")
        finally:
            del _browser_sessions[exec_id]

async def close_browser():
    """Safely closes the active browser session asynchronously."""
    try:
        exec_id = _active_execution_id.get()
        await close_browser_session(exec_id)
    except Exception:
        pass

async def detect_security_challenges(page) -> str | None:
    try:
        if page is None:
            return None
        print(f"[DEBUG] detect_security_challenges checking URL: {page.url}")
        html = await page.content() if page else ""
        print(f"[DEBUG] detect_security_challenges HTML length: {len(html)}")
        if "recaptcha" in html.lower() or "google.com/recaptcha" in html.lower():
            return "reCAPTCHA"
        if "hcaptcha" in html.lower() or "hcaptcha.com" in html.lower():
            return "hCaptcha"
        if "turnstile" in html.lower() or "challenges.cloudflare.com" in html.lower():
            return "Cloudflare Turnstile"
        
        mfa_keywords = ["one-time password", "otp", "verification code", "mfa code", "2fa code", "two-factor", "security code"]
        for kw in mfa_keywords:
            if kw in html.lower():
                return f"MFA/OTP check ({kw})"
    except Exception as e:
        print(f"[Browser] Error detecting security challenges: {e}")
        pass
    return None

async def check_and_handle_security_challenges(page, execution_id: str):
    challenge = await detect_security_challenges(page)
    if not challenge:
        return
        
    print(f"\n[Security Challenge Detected] {challenge}. Transitioning state to WAITING_FOR_USER.")
    
    try:
        from src.core.events import emit_event
        await emit_event("status_update", f"WAITING_FOR_USER: {challenge}")
    except Exception as e:
        print(f"Error emitting pause event: {e}")
        
    event = asyncio.Event()
    active_pauses[execution_id] = event
    print(f"[PAUSED] Execution ID: {execution_id}. Awaiting human input or REST api resume...")
    
    try:
        await event.wait()
        print(f"[RESUMED] Execution ID: {execution_id}. Human authentication complete. Resuming...")
    finally:
        if execution_id in active_pauses:
            del active_pauses[execution_id]

def resume_paused_execution(execution_id: str) -> bool:
    if execution_id in active_pauses:
        active_pauses[execution_id].set()
        return True
    return False

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
                        'class': valueOf(e, 'class'),
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
        
        return f"Visible interactable elements:\n{elements}"
    except Exception as e:
        return f"Failed to analyze page: {repr(e)}"


from urllib.parse import urlparse

def get_url_path() -> str:
    try:
        url = get_session().page.url
        parsed = urlparse(url)
        # Combine host and path to keep caches distinct across domains
        return f"{parsed.netloc}{parsed.path}"
    except Exception:
        return "unknown"

def get_locator(selector_str: str):
    page = get_session().page
    if selector_str.startswith("role="):
        role_part = selector_str[5:]
        if "[" in role_part:
            role = role_part.split("[")[0]
            name_part = role_part.split("name=")[1]
            name = name_part.rstrip("]")
            if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
                name = name[1:-1]
            return page.get_by_role(role, name=name, exact=False)
        else:
            return page.get_by_role(role_part)
    elif selector_str.startswith("label="):
        label_text = selector_str[6:]
        if (label_text.startswith('"') and label_text.endswith('"')) or (label_text.startswith("'") and label_text.endswith("'")):
            label_text = label_text[1:-1]
        return page.get_by_label(label_text, exact=False)
    elif selector_str.startswith("text="):
        text_val = selector_str[5:]
        if (text_val.startswith('"') and text_val.endswith('"')) or (text_val.startswith("'") and text_val.endswith("'")):
            text_val = text_val[1:-1]
        return page.get_by_text(text_val, exact=False)
    elif selector_str.startswith("placeholder="):
        ph_val = selector_str[12:]
        if (ph_val.startswith('"') and ph_val.endswith('"')) or (ph_val.startswith("'") and ph_val.endswith("'")):
            ph_val = ph_val[1:-1]
        return page.get_by_placeholder(ph_val, exact=False)
    else:
        return page.locator(selector_str)

async def self_heal_element(selector_or_text: str, element_type: str = "clickable") -> str | None:
    """Scans interactive elements on the page and heals selectors using heuristics & LLM fallback."""
    try:
        elements_info = await get_session().page.evaluate("""() => {
            const interactive = [
                'input:not([type="hidden"])',
                'textarea',
                'select',
                'button',
                'a',
                '[role="button"]',
                '[role="link"]',
                '[onclick]'
            ].join(',');
            return Array.from(document.querySelectorAll(interactive))
                .filter(e => {
                    const rect = e.getBoundingClientRect();
                    const style = window.getComputedStyle(e);
                    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                })
                .map((e, index) => {
                    const tag = e.tagName.toLowerCase();
                    const text = (e.innerText || e.value || '').trim().replace(/\\s+/g, ' ').substring(0, 50);
                    const id = e.id || '';
                    const name = e.getAttribute('name') || '';
                    const className = e.className || '';
                    const placeholder = e.getAttribute('placeholder') || '';
                    const label = e.labels && e.labels.length ? Array.from(e.labels).map(l => l.innerText.trim()).join(' ') : '';
                    const testid = e.getAttribute('data-testid') || '';
                    const role = e.getAttribute('role') || '';
                    const type = e.getAttribute('type') || '';
                    
                    let selector = '';
                    if (testid) selector = `[data-testid="${testid}"]`;
                    else if (id) selector = `#${id}`;
                    else if (name) selector = `[name="${name}"]`;
                    else if (placeholder) selector = `[placeholder="${placeholder}"]`;
                    else if (tag === 'button' && text) selector = `role=button[name="${text}"]`;
                    else if (tag === 'a' && text) selector = `role=link[name="${text}"]`;
                    else selector = `${tag}:nth-of-type(${index + 1})`;
                    
                    return { index, tag, text, id, name, placeholder, label, testid, role, type, selector, className };
                });
        }""")
        
        if not elements_info:
            return None
            
        best_score = 0
        best_element = None
        target = selector_or_text.lower()
        
        for el in elements_info:
            score = 0
            if el['testid'].lower() == target: score += 100
            if el['id'].lower() == target: score += 90
            if el['name'].lower() == target: score += 80
            if el.get('className', '').lower() == target: score += 80
            if el['placeholder'].lower() == target: score += 70
            if el['label'].lower() == target: score += 60
            if el['text'].lower() == target: score += 50
            
            if el['testid'] and target in el['testid'].lower(): score += 40
            if el.get('className') and target in el['className'].lower(): score += 35
            if el['id'] and target in el['id'].lower(): score += 30
            if el['name'] and target in el['name'].lower(): score += 25
            if el['placeholder'] and target in el['placeholder'].lower(): score += 20
            if el['label'] and target in el['label'].lower(): score += 15
            if el['text'] and target in el['text'].lower(): score += 10
            
            if element_type == "input" and el['tag'] in ('input', 'textarea', 'select'):
                score += 5
            elif element_type == "clickable" and (el['tag'] in ('button', 'a') or el['role'] in ('button', 'link')):
                score += 5
                
            if score > best_score:
                best_score = score
                best_element = el
                
        if best_score >= 50 and best_element:
            print(f"[Self-Healing] Strong heuristic match: {best_element['selector']} (Score: {best_score})")
            from src.core.stats import increment_heals
            increment_heals()
            return best_element['selector']
            
        print(f"[Self-Healing] Heuristics weak (Score: {best_score}). Requesting LLM selector fallback...")
        from src.agent.factory import build_llm
        llm = build_llm(model="llama-3.1-8b-instant", temperature=0)
        
        candidates_str = ""
        for el in elements_info[:15]:
            candidates_str += (
                f"Index: {el['index']} | Tag: <{el['tag']}> | ID: '{el['id']}' | Name: '{el['name']}' "
                f"| Class: '{el.get('className', '')}' | TestID: '{el['testid']}' | Label: '{el['label']}' | Placeholder: '{el['placeholder']}' "
                f"| Text: '{el['text']}' | Selector: '{el['selector']}'\n"
            )
            
        prompt = (
            "You are a Playwright self-healing locator assistant.\n"
            f"The user wants to find an element described as: '{selector_or_text}' (type: {element_type}).\n"
            "The original locator failed. Look at the visible candidate elements:\n\n"
            f"{candidates_str}\n"
            "Identify the correct element index that matches the user's intent. If none match, return -1.\n"
            "Output ONLY the integer index or -1 (no extra words, no explanation)."
        )
        
        response = await llm.ainvoke([("human", prompt)])
        resp = response.content.strip()
        try:
            match_index = int(resp)
            if match_index >= 0:
                for el in elements_info:
                    if el['index'] == match_index:
                        print(f"[Self-Healing] LLM resolved element to: {el['selector']} (Index: {match_index})")
                        from src.core.stats import increment_heals
                        increment_heals()
                        return el['selector']
        except ValueError:
            print(f"[Self-Healing] LLM matched invalid index: '{resp}'")
            
        if best_element and best_score >= 10:
            print(f"[Self-Healing] Fallback to best heuristic match: {best_element['selector']}")
            from src.core.stats import increment_heals
            increment_heals()
            return best_element['selector']
            
        return None
    except Exception as exc:
        print(f"[Self-Healing] Error occurred during matching: {exc}")
        return None

async def get_parent_anchor_for_element(locator) -> str:
    try:
        # Check parent node of the first matching element
        anchor = await locator.first.evaluate("""(element) => {
            let parent = element.parentElement;
            while (parent) {
                if (parent.id) return `${parent.tagName.toLowerCase()}#${parent.id}`;
                if (parent.getAttribute('data-testid')) return `[data-testid="${parent.getAttribute('data-testid')}"]`;
                const classes = Array.from(parent.classList).filter(c => !c.startsWith('rand-class-') && !c.startsWith('rand-class')).join('.');
                if (classes) return `${parent.tagName.toLowerCase()}.${classes}`;
                parent = parent.parentElement;
            }
            return 'body';
        }""")
        return anchor or 'body'
    except Exception:
        return 'body'

@tool
async def click_element(selector_or_text: str) -> str:
    """Clicks a button or link based on its text, name, aria-label, data-testid, or CSS selector."""
    try:
        from src.api.database import DatabaseManager
        url_path = get_url_path()
        exec_id = _active_execution_id.get("default_execution")
        await check_and_handle_security_challenges(get_session().page, exec_id)
        print(f"[Browser] AI clicking on '{selector_or_text}' (URL: {url_path})...")
        
        # 1. Try cache if memory is enabled
        if get_session().memory_enabled:
            candidates = DatabaseManager.get_cached_selectors(url_path, selector_or_text)
            candidates = sorted(candidates, key=lambda x: x.get("confidence_score", 1.0), reverse=True)
            for cand in candidates:
                parent = cand.get("parent_anchor", "body")
                resolved = cand.get("resolved_selector")
                try:
                    scoped_locator = get_locator(parent).locator(get_locator(resolved)).first
                    if await scoped_locator.count() > 0:
                        print(f"[Memory Cache] Hit context-aware selector inside '{parent}': {resolved}")
                        await scoped_locator.scroll_into_view_if_needed()
                        await scoped_locator.click(timeout=3000)
                        try:
                            await get_session().page.wait_for_load_state("domcontentloaded", timeout=2000)
                        except:
                            pass
                        DatabaseManager.save_selector_memory(url_path, selector_or_text, parent, resolved, success=True)
                        from src.core.stats import increment_cache_hit
                        increment_cache_hit()
                        return f"Successfully clicked on '{selector_or_text}' (via cache)"
                    else:
                        print(f"[Memory Cache] Cached selector '{resolved}' inside parent '{parent}' missing.")
                        DatabaseManager.save_selector_memory(url_path, selector_or_text, parent, resolved, success=False)
                except Exception as e:
                    print(f"[Memory Cache] Cache trial failed: {e}")
                    DatabaseManager.save_selector_memory(url_path, selector_or_text, parent, resolved, success=False)

        # 2. Try standard locators
        locators = [
            (f"[data-testid='{selector_or_text}']", get_session().page.locator(f"[data-testid='{selector_or_text}']")),
            (f"role=button[name='{selector_or_text}']", get_session().page.get_by_role("button", name=selector_or_text, exact=False)),
            (f"role=link[name='{selector_or_text}']", get_session().page.get_by_role("link", name=selector_or_text, exact=False)),
            (f"label='{selector_or_text}'", get_session().page.get_by_label(selector_or_text, exact=False)),
            (f"text='{selector_or_text}'", get_session().page.get_by_text(selector_or_text, exact=False)),
            (selector_or_text, get_session().page.locator(selector_or_text))
        ]

        for sel, locator in locators:
            try:
                if await locator.count() > 0:
                    target = locator.first
                    await target.scroll_into_view_if_needed()
                    parent_anchor = await get_parent_anchor_for_element(target)
                    await target.click(timeout=3000)
                    try:
                        await get_session().page.wait_for_load_state("domcontentloaded", timeout=2000)
                    except:
                        pass
                    if get_session().memory_enabled:
                        DatabaseManager.save_selector_memory(url_path, selector_or_text, parent_anchor, sel, success=True)
                    return f"Successfully clicked on '{selector_or_text}'"
            except Exception:
                continue

        # 3. Localized selector-level self-healing (Internalizes locator recovery loop)
        print(f"[Self-Healing] Click targets failed. Initiating local self-healing for '{selector_or_text}'...")
        if get_session().memory_enabled:
            from src.core.stats import increment_cache_miss
            increment_cache_miss()
        healed = await self_heal_element(selector_or_text, element_type="clickable")
        if healed:
            try:
                loc = get_locator(healed).first
                await loc.scroll_into_view_if_needed()
                parent_anchor = await get_parent_anchor_for_element(loc)
                await loc.click(timeout=5000)
                try:
                    await get_session().page.wait_for_load_state("domcontentloaded", timeout=2000)
                except:
                    pass
                if get_session().memory_enabled:
                    DatabaseManager.save_selector_memory(url_path, selector_or_text, parent_anchor, healed, success=True)
                return f"Successfully clicked on '{selector_or_text}' (self-healed to: {healed})"
            except Exception as e:
                print(f"[Self-Healing] Click failed on healed target '{healed}': {e}")

        return f"Failed to click '{selector_or_text}': no visible or clickable element found matching this description."
    except Exception as e:
        return f"Error during click operation: {repr(e)}"

@tool
async def fill_input(selector_or_placeholder: str, text: str) -> str:
    """Fills an input field by label, placeholder, id, name, or CSS selector."""
    try:
        from src.api.database import DatabaseManager
        url_path = get_url_path()
        exec_id = _active_execution_id.get("default_execution")
        await check_and_handle_security_challenges(get_session().page, exec_id)
        print(f"[Browser] AI typing '{text}' into '{selector_or_placeholder}' (URL: {url_path})...")
        
        # 1. Try cache if memory is enabled
        if get_session().memory_enabled:
            candidates = DatabaseManager.get_cached_selectors(url_path, selector_or_placeholder)
            candidates = sorted(candidates, key=lambda x: x.get("confidence_score", 1.0), reverse=True)
            for cand in candidates:
                parent = cand.get("parent_anchor", "body")
                resolved = cand.get("resolved_selector")
                try:
                    scoped_locator = get_locator(parent).locator(get_locator(resolved)).first
                    if await scoped_locator.count() > 0:
                        print(f"[Memory Cache] Hit context-aware selector inside '{parent}': {resolved}")
                        await scoped_locator.scroll_into_view_if_needed()
                        await scoped_locator.fill(text, timeout=3000)
                        DatabaseManager.save_selector_memory(url_path, selector_or_placeholder, parent, resolved, success=True)
                        from src.core.stats import increment_cache_hit
                        increment_cache_hit()
                        return f"Successfully filled '{selector_or_placeholder}' with text (via cache)"
                    else:
                        print(f"[Memory Cache] Cached selector '{resolved}' inside parent '{parent}' missing.")
                        DatabaseManager.save_selector_memory(url_path, selector_or_placeholder, parent, resolved, success=False)
                except Exception as e:
                    print(f"[Memory Cache] Cache trial failed: {e}")
                    DatabaseManager.save_selector_memory(url_path, selector_or_placeholder, parent, resolved, success=False)

        # 2. Try standard locators
        locators = [
            (f"[data-testid='{selector_or_placeholder}']", get_session().page.locator(f"[data-testid='{selector_or_placeholder}']")),
            (f"label='{selector_or_placeholder}'", get_session().page.get_by_label(selector_or_placeholder, exact=False)),
            (f"placeholder='{selector_or_placeholder}'", get_session().page.get_by_placeholder(selector_or_placeholder, exact=False)),
            (f"[name='{selector_or_placeholder}']", get_session().page.locator(f"[name='{selector_or_placeholder}']")),
            (f"#{selector_or_placeholder}", get_session().page.locator(f"#{selector_or_placeholder}")),
            (selector_or_placeholder, get_session().page.locator(selector_or_placeholder))
        ]

        for sel, locator in locators:
            try:
                if await locator.count() > 0:
                    target = locator.first
                    await target.scroll_into_view_if_needed()
                    parent_anchor = await get_parent_anchor_for_element(target)
                    await target.fill(text, timeout=3000)
                    if get_session().memory_enabled:
                        DatabaseManager.save_selector_memory(url_path, selector_or_placeholder, parent_anchor, sel, success=True)
                    return f"Successfully filled '{selector_or_placeholder}' with text."
            except Exception:
                continue

        # 3. Localized selector-level self-healing
        print(f"[Self-Healing] Fill targets failed. Initiating local self-healing for '{selector_or_placeholder}'...")
        if get_session().memory_enabled:
            from src.core.stats import increment_cache_miss
            increment_cache_miss()
        healed = await self_heal_element(selector_or_placeholder, element_type="input")
        if healed:
            try:
                loc = get_locator(healed).first
                await loc.scroll_into_view_if_needed()
                parent_anchor = await get_parent_anchor_for_element(loc)
                await loc.fill(text, timeout=5000)
                if get_session().memory_enabled:
                    DatabaseManager.save_selector_memory(url_path, selector_or_placeholder, parent_anchor, healed, success=True)
                return f"Successfully filled '{selector_or_placeholder}' with text (self-healed to: {healed})"
            except Exception as e:
                print(f"[Self-Healing] Fill failed on healed target '{healed}': {e}")

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
            from src.core.stats import increment_assertions_passed
            increment_assertions_passed()
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
