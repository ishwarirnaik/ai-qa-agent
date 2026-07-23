import playwright

with playwright.sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to the target URL
    page.goto("https://www.saucedemo.com/")

    # Fill the username input field
    page.fill("input[name='user-name']", "standard_user")

    # Fill the password input field
    page.fill("input[name='password']", "secret_sauce")

    # Click the login button
    page.click("text=Login")

    # Click the add to cart button for the Sauce Labs Backpack
    page.click("text=Add to cart for Sauce Labs Backpack")

    # Click the shopping cart button
    page.click("text=Shopping Cart")

    # Click the checkout button
    page.click("text=Checkout")

    # Fill the first name input field
    page.fill("input[name='first-name']", "Alice")

    # Analyze the page elements
    page.wait_for_load_state("networkidle0")
    elements = page.query_selector_all("button, a")
    print("Visible interactable elements:")
    for element in elements:
        print(element.tag_name, element.get_attribute("id"), element.get_attribute("class"))

    # Fill the first name input field using the data-test attribute
    page.fill("input[data-test='first-name']", "Alice")

    # Fill the last name input field using the data-test attribute
    page.fill("input[data-test='last-name']", "Smith")

    # Fill the postal code input field using the data-test attribute
    page.fill("input[data-test='postal-code']", "90210")

    # Click the continue button
    page.click("text=Continue")

    # Assert that the thank you message is visible
    page.wait_for_load_state("networkidle0")
    assert page.query_selector("text=Thank you for your order!") is not None

    # Navigate to the cart page
    page.goto("https://www.saucedemo.com/cart.html")

    # Click the checkout button
    page.click("text=Checkout")

    # Fill the first name input field using the data-test attribute
    page.fill("input[data-test='first-name']", "Alice")

    # Fill the last name input field using the data-test attribute
    page.fill("input[data-test='last-name']", "Smith")

    # Fill the postal code input field using the data-test attribute
    page.fill("input[data-test='postal-code']", "90210")

    # Click the continue button
    page.click("text=Continue")

    # Close the browser
    browser.close()