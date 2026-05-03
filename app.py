#revenue bot
import os
import pandas as pd
from io import BytesIO
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity


# ── Config ────────────────────────────────────────────────────────────────────
MICROSOFT_APP_ID       = os.environ.get("MICROSOFT_APP_ID", "")
MICROSOFT_APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
ADLS_ACCOUNT_NAME      = os.environ.get("ADLS_ACCOUNT_NAME", "")
ADLS_ACCOUNT_KEY       = os.environ.get("ADLS_ACCOUNT_KEY", "")
ADLS_FILESYSTEM        = os.environ.get("ADLS_FILESYSTEM", "data")
ADLS_FILE_PATH         = os.environ.get("ADLS_FILE_PATH", "revenue.xlsx")
# ─────────────────────────────────────────────────────────────────────────────

settings = BotFrameworkAdapterSettings(MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD)
adapter  = BotFrameworkAdapter(settings)


# ── Data loader ───────────────────────────────────────────────────────────────
def get_df() -> pd.DataFrame:
    try:
        from azure.storage.filedatalake import DataLakeServiceClient
        service = DataLakeServiceClient(
            account_url=f"https://{ADLS_ACCOUNT_NAME}.dfs.core.windows.net",
            credential=ADLS_ACCOUNT_KEY,
        )
        fs   = service.get_file_system_client(ADLS_FILESYSTEM)
        fc   = fs.get_file_client(ADLS_FILE_PATH)
        data = fc.download_file().readall()
        df   = pd.read_excel(BytesIO(data))
    except Exception:
        df = pd.read_csv(
            os.path.join(os.path.dirname(__file__), "sample_data.csv")
        )
    df.columns = df.columns.str.strip()
    return df


# ── Calculation engine ────────────────────────────────────────────────────────
def fmt(n: float) -> str:
    return f"{n:,.0f}"


def answer(user_text: str) -> str:
    df  = get_df()
    txt = user_text.lower().strip()

    # apply filters
    f = df.copy()
    for col in ["BU", "Region", "Product", "Month"]:
        for val in df[col].unique():
            if str(val).lower() in txt:
                f = f[f[col].str.lower() == str(val).lower()]

    rev    = f["Revenue"].sum()
    cost   = f["Cost"].sum()
    prof   = f["Profit"].sum()
    margin = round(prof / rev * 100, 1) if rev else 0

    if "margin" in txt:
        return f"Profit Margin: {margin}%"

    if "revenue" in txt and "profit" not in txt and "cost" not in txt:
        return f"Total Revenue: {fmt(rev)}"

    if "cost" in txt:
        return f"Total Cost: {fmt(cost)}"

    if "profit" in txt:
        return f"Total Profit: {fmt(prof)}\nMargin: {margin}%"

    if any(x in txt for x in ["top", "best", "highest"]):
        col = "Profit" if "profit" in txt else "Revenue"
        grp = (
            "Region"  if "region"  in txt else
            "Product" if "product" in txt else
            "Month"   if "month"   in txt else "BU"
        )
        m = f.groupby(grp)[col].sum()
        return f"Top {grp} by {col}: {m.idxmax()} — {fmt(m.max())}"

    if any(x in txt for x in ["compare", "vs", "versus"]):
        col = "Profit" if "profit" in txt else "Revenue"
        m   = f.groupby("BU")[col].sum().sort_values(ascending=False)
        rows = "\n".join(f"  • {k}: {fmt(v)}" for k, v in m.items())
        return f"{col} by BU:\n{rows}"

    if any(x in txt for x in ["trend", "monthly"]):
        col   = "Profit" if "profit" in txt else "Revenue"
        order = ["Jan","Feb","Mar","Apr","May","Jun",
                 "Jul","Aug","Sep","Oct","Nov","Dec"]
        m     = f.groupby("Month")[col].sum()
        m     = m.reindex([x for x in order if x in m.index])
        rows  = "\n".join(f"  • {k}: {fmt(v)}" for k, v in m.items())
        return f"Monthly {col}:\n{rows}"

    if any(x in txt for x in ["summary", "overview", "all"]):
        return (
            f"📊 Summary\n"
            f"  • Revenue : {fmt(rev)}\n"
            f"  • Cost    : {fmt(cost)}\n"
            f"  • Profit  : {fmt(prof)}\n"
            f"  • Margin  : {margin}%"
        )

    return (
        "Hi! I can answer:\n"
        "  • total revenue\n"
        "  • profit for Finance\n"
        "  • cost for India\n"
        "  • profit margin\n"
        "  • top BU by revenue\n"
        "  • compare BUs by profit\n"
        "  • monthly revenue trend\n"
        "  • summary for Retail"
    )


# ── Bot handler ───────────────────────────────────────────────────────────────
async def on_message(turn_context: TurnContext):
    reply = answer(turn_context.activity.text or "")
    await turn_context.send_activity(Activity(type="message", text=reply))


# ── Web server ────────────────────────────────────────────────────────────────
async def messages(req: web.Request) -> web.Response:
    if req.content_type != "application/json":
        return web.Response(status=415)
    body     = await req.json()
    activity = Activity().deserialize(body)
    auth_hdr = req.headers.get("Authorization", "")

    async def callback(tc: TurnContext):
        await on_message(tc)

    await adapter.process_activity(activity, auth_hdr, callback)
    return web.Response(status=200)


app = web.Application()
app.router.add_post("/api/messages", messages)
app.router.add_get("/", lambda r: web.Response(text="Revenue Bot is running!"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    web.run_app(app, host="0.0.0.0", port=port)
