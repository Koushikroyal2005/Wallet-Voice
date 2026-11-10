"""Two independent local merchant servers. Secrets stay on the Python server."""
import argparse,json,os,secrets
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse

def main():
    parser=argparse.ArgumentParser();parser.add_argument('merchant',choices=['railway','food']);parser.add_argument('--port',type=int);parser.add_argument('--wallet-url',default='http://localhost:8000');args=parser.parse_args()
    target=urlparse(args.wallet_url)
    if target.scheme!='http' or target.hostname not in {'localhost','127.0.0.1'} or target.username or target.password or target.path not in {'','/'}:raise SystemExit('Local demo requires a loopback wallet URL')
    railway=args.merchant=='railway';ident='demo-railway' if railway else 'demo-food'
    secret=os.environ.get('MERCHANT_KEY')
    if not secret:raise SystemExit('Set MERCHANT_KEY in this server process only')
    reference='local-'+secrets.token_hex(8)
    body={'order_reference':reference,'amount':125000 if railway else 40000,'currency':'INR','description':'Simulated railway ticket' if railway else 'Simulated food order','expires_at':(datetime.now(timezone.utc)+timedelta(minutes=12)).isoformat()}
    headers={'Content-Type':'application/json','X-Merchant-Id':ident,'X-Merchant-Key':secret,'Idempotency-Key':reference}
    def wallet(path,method='GET',data=None):
        req=Request(args.wallet_url.rstrip('/')+'/api/merchant/v1'+path,headers=headers,method=method,data=json.dumps(data).encode() if data else None)
        with urlopen(req,timeout=10) as response:return response.read()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/status':return self.proxy('/orders/'+reference)
            html='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Wallet-Voice demo merchant</title><style>body{font:18px system-ui;background:#f5f7fa;color:#16323c;max-width:520px;margin:10vh auto;padding:24px}button,a{display:inline-block;padding:16px;margin:8px 0}button{background:#16323c;color:white;border:0;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Demo MERCHANT checkout</h1><p>SIMULATED · No real booking or food delivery.</p><p>PRICE INR</p><button onclick="act('/create')">Save request to Wallet-Voice</button><p>You can leave after saving. Your request stays in the wallet for 12 minutes.</p><a id="wallet-link" href="http://localhost:8080" target="_blank" rel="noopener">Open Wallet-Voice</a><button onclick="act('/status','GET')">Check payment / order</button><button id="fulfill" disabled onclick="act('/fulfill')">Confirm simulated fulfillment</button><p id="status" role="status">Checkout not saved yet.</p><details><summary>Integration details</summary><pre id="details"></pre></details><script>async function act(path,method='POST'){try{let r=await fetch(path,{method});let data=await r.json();document.getElementById('details').textContent=JSON.stringify(data,null,2);document.getElementById('status').textContent=data.error || ({PENDING_PAYMENT:'Saved in Wallet-Voice. Waiting for your approval.',PAYMENT_PROCESSING:'Payment is processing. Check again shortly.',PAYMENT_CONFIRMED:'Payment confirmed. Merchant fulfillment is still pending.',FULFILLED:'Merchant confirmed simulated fulfillment.',EXPIRED:'Checkout expired. Create a fresh request.',CANCELLED:'Checkout cancelled.',PAYMENT_FAILED:'Payment failed. Review the request in Wallet-Voice.',REFUNDED:'Payment refunded.'}[data.order_status] || 'Check the order status again.');document.getElementById('fulfill').disabled=data.payment_status!=='SUCCEEDED';if(data.review_url)document.getElementById('wallet-link').href='http://localhost:8080'+data.review_url}catch(e){document.getElementById('status').textContent='Connection failed. Check status before retrying.'}}</script>'''.replace('MERCHANT','Railway' if railway else 'Kitchen').replace('PRICE',str(body['amount']/100))
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(html.encode())
        def do_POST(self):
            if self.headers.get('Host') not in {f'localhost:{port}',f'127.0.0.1:{port}'} or self.headers.get('Origin') not in {f'http://localhost:{port}',f'http://127.0.0.1:{port}'}:
                return self.send_error(403,'Use this local merchant page')
            if self.path=='/create':return self.proxy('/checkout-requests','POST',body)
            if self.path=='/fulfill':return self.proxy('/orders/'+reference+'/fulfillment','POST')
            self.send_error(404)
        def proxy(self,path,method='GET',data=None):
            try:content=wallet(path,method,data);status=200
            except HTTPError as e:content=json.dumps({'error':'Wallet-Voice rejected the request','status':e.code}).encode();status=e.code
            except Exception:content=b'{"error":"Wallet-Voice unavailable; check status before retrying"}';status=502
            self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(content)
    port=args.port or (8091 if railway else 8092)
    print(f'Local simulated {args.merchant} checkout: http://localhost:{port}')
    HTTPServer(('127.0.0.1',port),Handler).serve_forever()
if __name__=='__main__':main()
