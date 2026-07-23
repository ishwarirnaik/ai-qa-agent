import asyncio
from async_playwright import async_playwright
from playwright.async_api import Browser, Page

async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=False)
        page: Page = await browser.new_page()
        
        # Navigate to apple.com
        print("Navigating to apple.com")
        await page.goto("https://www.apple.com/")
        
        # Navigate to Product Page
        print("Navigating to iPhone 14 Pro product page")
        await page.click("text='Shop and Learn'")
        await page.click("text='iPhone'")
        await page.click("text='iPhone 14 Pro'")
        
        # Select Product Options
        print("Selecting product options: 128GB, Space Gray")
        try:
            await page.click("text='128GB'")
            await page.click("text='Space Gray'")
        except Exception as e:
            print(f"Error selecting product options: {e}")
        
        # Click Add to Cart Button
        print("Clicking Add to Cart button")
        try:
            await page.click("text='Add to Bag'")
        except Exception as e:
            print(f"Error clicking Add to Cart button: {e}")
        
        # Verify Cart Contents
        print("Verifying cart contents")
        try:
            await page.click("text='Bag'")
            await page.wait_for_selector("text='iPhone 14 Pro'")
            print("Product found in cart")
        except Exception as e:
            print(f"Error verifying cart contents: {e}")
        
        # Verify Cart Summary
        print("Verifying cart summary")
        try:
            await page.wait_for_selector("text='Subtotal'")
            await page.wait_for_selector("text='Total'")
            print("Cart summary verified")
        except Exception as e:
            print(f"Error verifying cart summary: {e}")
        
        # Take screenshot
        print("Taking screenshot")
        await page.screenshot(path="evidence.png")
        
        # Close browser
        print("Closing browser")
        await browser.close()

asyncio.run(main())