import logging
import azure.functions as func
import os
import json
import pandas as pd
from io import BytesIO
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
import asyncio

APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
APP_PW = os.environ.get("MICROSOFT_APP_PASSWORD", "")

settings = BotFrameworkAdapterSettings(APP_ID, APP_PW)
adapter = BotFrameworkAdapter(settings)

def get_df():
    base = os.path.dirname(os.path.abspath(__file__))
    return pd.read_csv(os.path.join(base, '..', 'sample_data.csv'))

def answer(txt):
    df = get_df()
    t = txt.lower()
    f = df.copy()
    for col in ['BU', 'Region', 'Product', 'Month']:
        for val in df[col].unique():
            if str(val).lower() in t:
                f = f[f[col].str.lower() == str(val).lower()]
    rev = f['Revenue'].sum()
    cost = f['Cost'].sum()
    prof = f['Profit'].sum()
    margin = round(prof / rev * 100, 1) if rev else 0
    if 'margin' in t: return f'Profit Margin: {margin}%'
    if 'revenue' in t and 'profit' not in t and 'cost' not in t: return f'Total Revenue: {rev:,.0f}'
    if 'cost' in t: return f'Total Cost: {cost:,.0f}'
    if 'profit' in t: return f'Total Profit: {prof:,.0f} | Margin: {margin}%'
    if any(x in t for x in ['top', 'best']):
        col = 'Profit' if 'profit' in t else 'Revenue'
        grp = 'Region' if 'region' in t else 'Product' if 'product' in t else 'BU'
        m = f.groupby(grp)[col].sum()
        return f'Top {grp} by {col}: {m.idxmax()} with {m.max():,.0f}'
    if 'compare' in t or 'vs' in t:
        m = f.groupby('BU')['Revenue'].sum().sort_values(ascending=False)
        return 'Revenue by BU:\n' + '\n'.join(f'  {k}: {v:,.0f}' for k, v in m.items())
    if any(x in t for x in ['summary', 'overview']):
        return f'Summary\n  Revenue: {rev:,.0f}\n  Cost: {cost:,.0f}\n  Profit: {prof:,.0f}\n  Margin: {margin}%'
    return 'Try: total revenue, profit for Finance, top BU, compare BUs, summary'

async def on_message(turn_context: TurnContext):
    reply = answer(turn_context.activity.text or "")
    await turn_context.send_activity(Activity(type="message", text=reply))

async def process(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body()
    activity = Activity().deserialize(json.loads(body))
    auth_header = req.headers.get("Authorization", "")
    
    async def callback(tc: TurnContext):
        await on_message(tc)
    
    await adapter.process_activity(activity, auth_header, callback)
    return func.HttpResponse(status_code=200)

def main(req: func.HttpRequest) -> func.HttpResponse:
    return asyncio.get_event_loop().run_until_complete(process(req))
