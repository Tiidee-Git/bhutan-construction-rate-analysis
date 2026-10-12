from pathlib import Path
import sqlite3
import os
import requests
from dotenv import load_dotenv
load_dotenv()
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
DB = ROOT / "rate_analysis.db"
app = FastAPI(title="Bhutan Construction Rate Analysis Tool", version="1.0.0")

@contextmanager
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db() as c:
        c.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS bsr_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_code TEXT NOT NULL UNIQUE,
          description TEXT NOT NULL,
          unit TEXT NOT NULL,
          bsr_edition TEXT DEFAULT 'Unverified / user supplied',
          town TEXT DEFAULT '',
          source_name TEXT DEFAULT '',
          verification_date TEXT DEFAULT '',
          overhead_pct REAL NOT NULL DEFAULT 5,
          profit_pct REAL NOT NULL DEFAULT 10
        );
        CREATE TABLE IF NOT EXISTS item_components (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_id INTEGER NOT NULL REFERENCES bsr_items(id) ON DELETE CASCADE,
          component_type TEXT NOT NULL CHECK(component_type IN ('Material','Labor','Equipment')),
          component_name TEXT NOT NULL,
          unit TEXT NOT NULL DEFAULT '',
          coefficient REAL NOT NULL DEFAULT 0,
          unit_rate REAL NOT NULL DEFAULT 0,
          UNIQUE(item_id, component_type, component_name)
        );
        """)
        count = c.execute("SELECT COUNT(*) FROM bsr_items").fetchone()[0]
        if count == 0:
            # Illustrative demo rows only. Replace/import verified MOIT BSR/LMC data before official use.
            demo = [
              ("DEMO-CIV-001","Plain cement concrete, illustrative demo item","m³","DEMO ONLY — not an official BSR","","Illustrative sample", "","",5,10),
              ("DEMO-CIV-002","Brick masonry, illustrative demo item","m³","DEMO ONLY — not an official BSR","","Illustrative sample","","",5,10),
              ("DEMO-CIV-003","Reinforced concrete work, illustrative demo item","m³","DEMO ONLY — not an official BSR","","Illustrative sample","","",5,10),
            ]
            for row in demo:
                c.execute("""INSERT INTO bsr_items(item_code,description,unit,bsr_edition,town,source_name,verification_date,overhead_pct,profit_pct)
                             VALUES(?,?,?,?,?,?,?,?,?)""", row)
            ids = {r["item_code"]: r["id"] for r in c.execute("SELECT id,item_code FROM bsr_items")}
            comps = [
              (ids["DEMO-CIV-001"],"Material","Cement","bag",1.8,420),
              (ids["DEMO-CIV-001"],"Material","Sand","m³",0.45,1800),
              (ids["DEMO-CIV-001"],"Material","Coarse aggregate","m³",0.9,2100),
              (ids["DEMO-CIV-001"],"Labor","Mason","day",0.35,900),
              (ids["DEMO-CIV-001"],"Labor","Helper","day",0.6,600),
              (ids["DEMO-CIV-001"],"Equipment","Concrete mixer","hour",0.25,700),
              (ids["DEMO-CIV-002"],"Material","Bricks","each",500,12),
              (ids["DEMO-CIV-002"],"Material","Cement mortar allowance","item",1,1250),
              (ids["DEMO-CIV-002"],"Labor","Mason","day",1.2,900),
              (ids["DEMO-CIV-002"],"Labor","Helper","day",1.5,600),
              (ids["DEMO-CIV-003"],"Material","Cement","bag",7,420),
              (ids["DEMO-CIV-003"],"Material","Sand","m³",0.45,1800),
              (ids["DEMO-CIV-003"],"Material","Coarse aggregate","m³",0.9,2100),
              (ids["DEMO-CIV-003"],"Material","Reinforcement steel","kg",80,95),
              (ids["DEMO-CIV-003"],"Labor","Steel fixer","day",1.2,950),
              (ids["DEMO-CIV-003"],"Labor","Carpenter","day",1.0,900),
              (ids["DEMO-CIV-003"],"Labor","Helper","day",1.8,600),
              (ids["DEMO-CIV-003"],"Equipment","Concrete vibrator","hour",0.5,450),
            ]
            c.executemany("""INSERT INTO item_components(item_id,component_type,component_name,unit,coefficient,unit_rate)
                             VALUES(?,?,?,?,?,?)""", comps)

class ItemIn(BaseModel):
    item_code: str
    description: str
    unit: str
    bsr_edition: str = "User supplied"
    town: str = ""
    source_name: str = ""
    verification_date: str = ""
    overhead_pct: float = Field(default=5, ge=0, le=100)
    profit_pct: float = Field(default=10, ge=0, le=100)
    components: list[dict] = []

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {"status":"ok","database":"SQLite","demo_data":"Illustrative only; not official BSR/LMC data"}

@app.get("/api/items")
def list_items(q: str = ""):
    with db() as c:
        rows = c.execute("""SELECT * FROM bsr_items
          WHERE item_code LIKE ? OR description LIKE ? ORDER BY item_code""",
          (f"%{q}%", f"%{q}%")).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/items/{item_code}")
def get_item(item_code: str):
    with db() as c:
        row = c.execute("SELECT * FROM bsr_items WHERE item_code=?", (item_code,)).fetchone()
        if not row: raise HTTPException(404, "Item code not found")
        item = dict(row)
        item["components"] = [dict(x) for x in c.execute(
          "SELECT component_type,component_name,unit,coefficient,unit_rate FROM item_components WHERE item_id=? ORDER BY CASE component_type WHEN 'Material' THEN 1 WHEN 'Labor' THEN 2 ELSE 3 END, component_name",
          (item["id"],)).fetchall()]
        return item

@app.post("/api/items")
def create_or_replace_item(payload: ItemIn):
    with db() as c:
        c.execute("""INSERT INTO bsr_items(item_code,description,unit,bsr_edition,town,source_name,verification_date,overhead_pct,profit_pct)
          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(item_code) DO UPDATE SET description=excluded.description,unit=excluded.unit,
          bsr_edition=excluded.bsr_edition,town=excluded.town,source_name=excluded.source_name,
          verification_date=excluded.verification_date,overhead_pct=excluded.overhead_pct,profit_pct=excluded.profit_pct""",
          (payload.item_code,payload.description,payload.unit,payload.bsr_edition,payload.town,payload.source_name,payload.verification_date,payload.overhead_pct,payload.profit_pct))
        item_id = c.execute("SELECT id FROM bsr_items WHERE item_code=?", (payload.item_code,)).fetchone()["id"]
        c.execute("DELETE FROM item_components WHERE item_id=?", (item_id,))
        for x in payload.components:
            c.execute("""INSERT INTO item_components(item_id,component_type,component_name,unit,coefficient,unit_rate)
              VALUES(?,?,?,?,?,?)""",(item_id,x["component_type"],x["component_name"],x.get("unit",""),float(x.get("coefficient",0)),float(x.get("unit_rate",0))))
        return {"saved":True,"item_code":payload.item_code}

@app.delete("/api/items/{item_code}")
def delete_item(item_code: str):
    with db() as c:
        cur=c.execute("DELETE FROM bsr_items WHERE item_code=?", (item_code,))
        if not cur.rowcount: raise HTTPException(404,"Item code not found")
        return {"deleted":True}


class AIDraftIn(BaseModel):
    description: str
    unit: str
    discipline: str = "civil"
    town: str = ""
    project_context: str = ""
    known_rates: list[dict] = []

@app.post("/api/ai/draft-rate")
def ai_draft_rate(payload: AIDraftIn):
    """Return a provisional AI breakdown; never save it into official records automatically."""
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "AI is not configured. Set AI_API_KEY in your server .env file.")
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("AI_MODEL", "gpt-4.1-mini")
    system_prompt = (
      "You are an assistant for Bhutan construction rate analysis. Produce a DRAFT engineering estimate, "
      "not an official BSR/LMC rate. Never invent official item codes or claim the values are from MoIT. "
      "Use only known_rates as supplied reference prices; if no reliable prices are supplied, clearly label "
      "any estimated unit prices as assumptions requiring local supplier/labour quotation verification. "
      "Explain assumptions and uncertainties. Return valid JSON only with keys: item_description, discipline, "
      "unit, status (must be 'AI DRAFT — NOT OFFICIAL'), components (array of objects with component_type "
      "(Material/Labor/Equipment), component_name, unit, coefficient, unit_rate, amount, basis), "
      "direct_cost, overhead_pct, overhead_amount, profit_pct, profit_amount, estimated_unit_rate, "
      "missing_information (array), assumptions (array), review_checklist (array). "
      "All numeric values must be nonnegative. Use Bhutan context and Nu. amounts. Do not claim professional "
      "certification; require review by a qualified engineer."
    )
    user_payload = {
      "description": payload.description, "unit": payload.unit, "discipline": payload.discipline,
      "town": payload.town, "project_context": payload.project_context, "known_rates": payload.known_rates,
      "instruction": "Prepare a transparent provisional rate analysis. Coefficients must be stated per one unit of work."
    }
    try:
      response = requests.post(
        base_url + "/chat/completions",
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        json={"model": model, "temperature": 0.2, "response_format": {"type":"json_object"},
              "messages":[{"role":"system","content":system_prompt},
                          {"role":"user","content":__import__("json").dumps(user_payload, ensure_ascii=False)}]},
        timeout=90
      )
      response.raise_for_status()
      data = response.json()
      content = data["choices"][0]["message"]["content"]
      import json
      draft = json.loads(content)
      draft["status"] = "AI DRAFT — NOT OFFICIAL"
      draft["source_name"] = "AI-generated draft; not an official MoIT source"
      draft["review_required"] = True
      return draft
    except requests.RequestException as e:
      raise HTTPException(502, f"AI provider request failed: {str(e)[:300]}")
    except (KeyError, ValueError, TypeError) as e:
      raise HTTPException(502, "AI provider returned an invalid response. Try again or check the configured model.")

app.mount("/static", StaticFiles(directory=ROOT/"static"), name="static")
@app.get("/")
def home():
    return FileResponse(ROOT/"static"/"index.html")
