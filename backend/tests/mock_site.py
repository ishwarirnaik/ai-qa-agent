import random
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    mfa = request.query_params.get("mfa") == "true"
    
    username_placeholder = f"Enter Username ({rand_str})"
    password_placeholder = f"Enter Password ({rand_str})"
    button_text = f"Sign In ({rand_str})"
    
    username_html = f"""
      <div style="margin-bottom: 1rem;">
        <label for="input_usr_{rand_str}">Username</label>
        <input type="text" id="input_usr_{rand_str}" name="field_user_{rand_str}" placeholder="{username_placeholder}" required />
      </div>
    """
    
    password_html = f"""
      <div style="margin-bottom: 1rem;">
        <label for="input_pwd_{rand_str}">Password</label>
        <input type="password" id="input_pwd_{rand_str}" name="field_pass_{rand_str}" placeholder="{password_placeholder}" required />
      </div>
    """
    
    button_html = f"""
      <button type="submit" id="btn_submit_{rand_str}">{button_text}</button>
    """
    
    if drift:
        username_placeholder = f"User Identifier ({rand_str})"
        password_placeholder = f"Secret Access Code ({rand_str})"
        button_text = f"Secure Access Entry ({rand_str})"
        
        username_html = f"""
        <div class="nested-wrapper-{rand_str}" style="padding: 2px; border: 1px solid #334155; margin-bottom: 0.5rem;">
            <div class="field-container-usr">
                <label for="input_usr_{rand_str}">Username ID</label>
                <input type="text" id="input_usr_{rand_str}" name="field_user_{rand_str}" placeholder="{username_placeholder}" required />
            </div>
        </div>
        """
        
        password_html = f"""
        <div class="nested-wrapper-{rand_str}" style="padding: 2px; border: 1px solid #334155; margin-bottom: 0.5rem;">
            <div class="field-container-pwd">
                <input type="password" id="input_pwd_{rand_str}" name="field_pass_{rand_str}" placeholder="{password_placeholder}" required />
                <label for="input_pwd_{rand_str}">Secret Key</label>
            </div>
        </div>
        """
        
        button_html = f"""
        <div class="btn-relocator-{rand_str}" style="margin-top: 1rem;">
            <button type="submit" id="btn_submit_{rand_str}" style="background: #10b981;">{button_text}</button>
        </div>
        """
    
    form_elements = [username_html, password_html]
    if drift:
        form_elements = [password_html, username_html]
        
    form_content = "\n".join(form_elements) + "\n" + button_html
    
    if mfa:
        form_content = f"""
        <div style="background: #334155; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; text-align: center;">
            <h4 style="color: #ef4444; margin-top: 0;">MFA Verification Required</h4>
            <iframe src="https://google.com/recaptcha/api2/anchor?k=mock_key" style="border: 0; width: 100%; height: 80px;"></iframe>
            <label for="otp_code">Enter OTP verification code (MFA)</label>
            <input type="text" id="otp_code" name="otp_code" placeholder="Enter 6-digit OTP code" style="margin-top: 0.5rem;" />
        </div>
        """ + form_content

    html_content = f"""
    <html>
      <head>
        <title>Mock Secure App - Login</title>
        <style>
          body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
          .card {{ background: #1e293b; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); width: 320px; }}
          input {{ width: 100%; padding: 0.5rem; margin-top: 0.5rem; margin-bottom: 1rem; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing: border-box; }}
          button {{ width: 100%; padding: 0.75rem; background: #3b82f6; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; }}
          button:hover {{ background: #2563eb; }}
          label {{ font-size: 0.875rem; color: #94a3b8; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h2>Secure Login</h2>
          <form action="/login" method="post">
            {form_content}
          </form>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/login")
async def handle_login(request: Request):
    form_data = await request.form()
    username = ""
    password = ""
    for k, v in form_data.items():
        if "user" in k:
            username = v
        elif "pass" in k:
            password = v
            
    if username == "admin" and password == "admin123":
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        return HTMLResponse(content="""
        <html>
          <body style="font-family: sans-serif; background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh;">
            <div style="color: #ef4444; font-size: 1.25rem; margin-bottom: 1rem;">Invalid Credentials!</div>
            <a href="/login" style="color: #3b82f6; text-decoration: none;">Try again</a>
          </body>
        </html>
        """)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    rand_str = f"{random.randint(1000, 9999)}"
    html_content = f"""
    <html>
      <head>
        <title>Mock Secure App - Dashboard</title>
        <style>
          body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
          .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; padding: 2rem; border-radius: 8px; }}
          .btn-checkout {{ display: inline-block; padding: 0.75rem 1.5rem; background: #10b981; color: white; text-decoration: none; border-radius: 4px; font-weight: bold; }}
          .btn-checkout:hover {{ background: #059669; }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Welcome, Admin!</h1>
          <p>This is your protected dashboard. You have successfully navigated dynamic selector drift.</p>
          <div style="margin-top: 2rem;">
            <a href="/checkout" class="btn-checkout rand-class-{rand_str}" id="checkout_link_{rand_str}">Process Transaction ({rand_str})</a>
          </div>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/checkout", response_class=HTMLResponse)
async def checkout_page():
    rand_str = f"{random.randint(1000, 9999)}"
    html_content = f"""
    <html>
      <head>
        <title>Mock Secure App - Checkout</title>
        <style>
          body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
          .container {{ max-width: 500px; margin: 0 auto; background: #1e293b; padding: 2rem; border-radius: 8px; }}
          input {{ width: 100%; padding: 0.5rem; margin-top: 0.5rem; margin-bottom: 1rem; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing: border-box; }}
          button {{ width: 100%; padding: 0.75rem; background: #ef4444; border: none; border-radius: 4px; color: white; font-weight: bold; cursor: pointer; }}
          button:hover {{ background: #dc2626; }}
        </style>
      </head>
      <body>
        <div class="container">
          <h2>Secure Checkout</h2>
          <form action="/checkout" method="post">
            <label for="cc_{rand_str}">Credit Card Number</label>
            <input type="text" id="cc_{rand_str}" name="card_{rand_str}" placeholder="1111-2222-3333-4444" required />
            <button type="submit" id="btn_pay_{rand_str}">Pay Now ({rand_str})</button>
          </form>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/checkout", response_class=HTMLResponse)
async def handle_checkout():
    html_content = """
    <html>
      <head>
        <title>Mock Secure App - Success</title>
        <style>
          body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
          .card {{ background: #1e293b; padding: 2rem; border-radius: 8px; text-align: center; }}
          h1 {{ color: #10b981; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h1>Success!</h1>
          <p>Your payment was processed successfully. Checkout complete!</p>
          <div id="payment-success-msg">Thank you for your purchase!</div>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- Form Submission Workflow ---
@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    
    name_label, name_id = "Full Name", f"name_{rand_str}"
    topic_label, topic_id = "Support Topic", f"topic_{rand_str}"
    submit_btn = f"Send Message ({rand_str})"
    
    if drift:
        name_label, name_id = "Legal Identity", f"n_{rand_str}_drift"
        topic_label, topic_id = "Reason for Inquiry", f"t_{rand_str}_drift"
        submit_btn = f"Dispatch ({rand_str})"
        
    html = f"""
    <html>
      <head><style>body{{font-family:sans-serif; background:#0f172a; color:#fff; padding:2rem;}} .form-box{{background:#1e293b; padding:2rem; max-width:400px; margin:auto;}} input, select, button{{display:block; width:100%; margin:10px 0; padding:8px;}} button{{background:#3b82f6; color:#fff; border:none;}}</style></head>
      <body>
        <div class="form-box">
          <h2>Contact Us</h2>
          <form action="/contact-success" method="post">
            <label for="{name_id}">{name_label}</label>
            <input type="text" id="{name_id}" name="name" required />
            
            <label for="{topic_id}">{topic_label}</label>
            <select id="{topic_id}" name="topic">
                <option value="billing">Billing</option>
                <option value="tech">Technical Support</option>
                <option value="general">General</option>
            </select>
            
            <button type="submit" id="btn_submit_{rand_str}">{submit_btn}</button>
          </form>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/contact-success", response_class=HTMLResponse)
async def contact_success():
    return HTMLResponse(content="<html><body style='background:#0f172a; color:#10b981; text-align:center; padding:5rem;'><h1>Message Received!</h1><div id='success-banner'>We will get back to you soon.</div></body></html>")


# --- Search Interaction Workflow ---
@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    query = request.query_params.get("q", "")
    
    input_id = f"search_in_{rand_str}" if not drift else f"s_{rand_str}_q"
    btn_id = f"search_btn_{rand_str}" if not drift else f"b_{rand_str}_s"
    
    results_html = ""
    if query:
        results_html = f"""
        <div id="search-results" style="margin-top:2rem;">
            <h3>Results for '{query}'</h3>
            <div class="result-item" style="padding:1rem; background:#334155; margin-bottom:1rem;">
                <h4>Mock Product A</h4>
                <p>Matches your search.</p>
            </div>
        </div>
        """
        
    html = f"""
    <html>
      <head><style>body{{font-family:sans-serif; background:#0f172a; color:#fff; padding:2rem;}} .search-box{{display:flex; gap:10px;}} input{{flex:1; padding:10px;}} button{{padding:10px 20px; background:#10b981; color:#fff; border:none;}}</style></head>
      <body>
        <h2>Search Directory</h2>
        <form action="/search" method="get" class="search-box">
            <input type="text" id="{input_id}" name="q" placeholder="Search products..." value="{query}" />
            <input type="hidden" name="drift" value="{request.query_params.get('drift', '')}" />
            <button type="submit" id="{btn_id}">Search</button>
        </form>
        {results_html}
      </body>
    </html>
    """
    return HTMLResponse(content=html)


# --- Multi-step Navigation Workflow ---
@app.get("/wizard/step1", response_class=HTMLResponse)
async def wizard_step1(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    link_id = f"next_{rand_str}" if not drift else f"n_{rand_str}_btn"
    url = f"/wizard/step2?drift=extreme" if drift else "/wizard/step2"
    
    return HTMLResponse(content=f"<html><body style='background:#0f172a; color:#fff; padding:2rem;'><h2>Step 1: Welcome</h2><p>Start the process.</p><a id='{link_id}' href='{url}' style='color:#3b82f6;'>Go to Step 2</a></body></html>")

@app.get("/wizard/step2", response_class=HTMLResponse)
async def wizard_step2(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    link_id = f"next_{rand_str}" if not drift else f"n_{rand_str}_btn"
    url = f"/wizard/step3?drift=extreme" if drift else "/wizard/step3"
    
    return HTMLResponse(content=f"<html><body style='background:#0f172a; color:#fff; padding:2rem;'><h2>Step 2: Details</h2><p>Almost done.</p><a id='{link_id}' href='{url}' style='color:#3b82f6;'>Go to Step 3</a></body></html>")

@app.get("/wizard/step3", response_class=HTMLResponse)
async def wizard_step3(request: Request):
    return HTMLResponse(content="<html><body style='background:#0f172a; color:#10b981; padding:2rem;'><h2 id='wizard-complete'>Wizard Complete!</h2><p>You made it to the end.</p></body></html>")


# --- E-commerce Navigation Workflow (Expanded) ---
@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    add_btn_id = f"add_to_cart_{rand_str}" if not drift else f"a2c_{rand_str}"
    
    url = f"/cart?drift=extreme" if drift else "/cart"
    
    html = f"""
    <html>
      <head><style>body{{font-family:sans-serif; background:#0f172a; color:#fff; padding:2rem;}} .product{{background:#1e293b; padding:1rem; width:200px;}} .btn{{display:inline-block; padding:8px 16px; background:#3b82f6; color:#fff; text-decoration:none; margin-top:10px;}}</style></head>
      <body>
        <h2>Products</h2>
        <div class="product">
            <h3>Smartphone X</h3>
            <p>$999</p>
            <a id="{add_btn_id}" href="{url}" class="btn">Add to Cart</a>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    rand_str = f"{random.randint(1000, 9999)}"
    drift = request.query_params.get("drift") == "extreme"
    chk_btn_id = f"checkout_{rand_str}" if not drift else f"chk_{rand_str}"
    
    url = f"/checkout?drift=extreme" if drift else "/checkout"
    
    html = f"""
    <html>
      <head><style>body{{font-family:sans-serif; background:#0f172a; color:#fff; padding:2rem;}} .btn{{display:inline-block; padding:8px 16px; background:#10b981; color:#fff; text-decoration:none; margin-top:20px;}}</style></head>
      <body>
        <h2>Shopping Cart</h2>
        <ul><li>1x Smartphone X - $999</li></ul>
        <a id="{chk_btn_id}" href="{url}" class="btn">Proceed to Checkout</a>
      </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
