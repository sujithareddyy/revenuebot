# Revenue Bot v4
import os
import pandas as pd
from flask import Flask, request, Response
import requests as req

APP_ID = os.environ.get('MICROSOFT_APP_ID', '')
APP_PW = os.environ.get('MICROSOFT_APP_PASSWORD', '')
TENANT_ID = os.environ.get('TENANT_ID', '')
app = Flask(__name__)

def get_df():
    return pd.read_csv('/home/site/wwwroot/sample_data.csv')

def answer(txt):
    df = get_df()
    t = txt.lower()
    f = df.copy()
    for col in ['BU','Region','Product','Month']:
        for val in df[col].unique():
            if str(val).lower() in t:
                f = f[f[col].str.lower()==str(val).lower()]
    rev = f['Revenue'].sum()
    cost = f['Cost'].sum()
    prof = f['Profit'].sum()
    margin = round(prof/rev*100,1) if rev else 0
    if 'margin' in t: return f'Profit Margin: {margin}%'
    if 'revenue' in t and 'profit' not in t and 'cost' not in t: return f'Total Revenue: {rev:,.0f}'
    if 'cost' in t: return f'Total Cost: {cost:,.0f}'
    if 'profit' in t: return f'Total Profit: {prof:,.0f} Margin: {margin}%'
    if any(x in t for x in ['top','best']):
        col = 'Profit' if 'profit' in t else 'Revenue'
        grp = 'Region' if 'region' in t else 'Product' if 'product' in t else 'BU'
        m = f.groupby(grp)[col].sum()
        return f'Top {grp} by {col}: {m.idxmax()} with {m.max():,.0f}'
    if 'compare' in t or 'vs' in t:
        m = f.groupby('BU')['Revenue'].sum().sort_values(ascending=False)
        return 'Revenue by BU:\n' + '\n'.join(f'  {k}: {v:,.0f}' for k,v in m.items())
    if any(x in t for x in ['summary','overview']):
        return f'Summary\n  Revenue: {rev:,.0f}\n  Cost: {cost:,.0f}\n  Profit: {prof:,.0f}\n  Margin: {margin}%'
    return 'Try: total revenue, profit for Finance, top BU, compare BUs, summary'

def get_token():
    r = req.post(f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token',
        data={'grant_type':'client_credentials','client_id':APP_ID,'client_secret':APP_PW,'scope':'https://api.botframework.com/.default'})
    return r.json().get('access_token','')

@app.route('/api/messages', methods=['POST'])
def messages():
    try:
        body = request.get_json(force=True)
        if body.get('type') == 'message':
            text = body.get('text','')
            reply_text = answer(text)
            service_url = body.get('serviceUrl','')
            conv_id = body.get('conversation',{}).get('id','')
            activity_id = body.get('id','')
            reply = {'type':'message','conversation':{'id':conv_id},'from':body.get('recipient',{}),'recipient':body.get('from',{}),'replyToId':activity_id,'text':reply_text}
            token = get_token()
            resp = req.post(f'{service_url}/v3/conversations/{conv_id}/activities/{activity_id}',json=reply,headers={'Authorization':f'Bearer {token}'})
    except Exception as e:
        print(f'Error: {e}')
    return Response(status=200)

@app.route('/')
def home():
    return 'Revenue Bot is running!'