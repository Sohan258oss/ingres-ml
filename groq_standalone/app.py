import ast
import base64
import io
import json
import os
import re
import sqlite3
import textwrap
import traceback
import uuid
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "groundwater_data.db"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
) if GROQ_API_KEY else None

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


SYSTEM_PROMPT = """
You are an Indian Groundwater Data engine.

Non-negotiable rules:
1. Never guess, infer, fabricate, or memorize numerical values.
2. The only valid source of numeric truth is the SQLite database `groundwater_data.db`.
3. If the user asks for a calculation, filtering, ranking, comparison, chart, table, trend, PDF, or list of districts/states, respond ONLY with a single executable Python script inside one ```python markdown block.
4. If the user asks a conceptual question that does not need database values, answer in concise markdown.
5. Generated Python must use the provided `connect_db()` helper to read the database.
6. Generated Python may use pandas, matplotlib.pyplot as plt, seaborn as sns, and reportlab.
7. Generated Python must save charts to `CHART_PATH` and PDFs to `REPORT_PATH`.
8. Generated Python must print a concise markdown summary to stdout.
9. Do not use network, file deletion, shell commands, environment variables, or arbitrary file access.

Database table:
district_assessments(
  id INTEGER,
  state_name TEXT,
  district_name TEXT,
  annual_extractable_mcm REAL,
  total_extraction_mcm REAL,
  stage_extraction_percentage REAL,
  status_category TEXT
)
"""


ALLOWED_IMPORTS = {
    "sqlite3",
    "pandas",
    "matplotlib",
    "matplotlib.pyplot",
    "seaborn",
    "reportlab",
    "reportlab.lib.pagesizes",
    "reportlab.pdfgen",
    "reportlab.pdfgen.canvas",
}

FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "input",
    "globals", "locals", "vars", "dir", "help", "breakpoint",
}


class SafetyVisitor(ast.NodeVisitor):
    def visit_Import(self, node):
        for alias in node.names:
            if alias.name not in ALLOWED_IMPORTS:
                raise ValueError(f"Import not allowed: {alias.name}")

    def visit_ImportFrom(self, node):
        module = node.module or ""
        if module not in ALLOWED_IMPORTS:
            raise ValueError(f"Import not allowed: {module}")

    def visit_Name(self, node):
        if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
            raise ValueError(f"Forbidden name: {node.id}")

    def visit_Attribute(self, node):
        if node.attr.startswith("__"):
            raise ValueError("Dunder attributes are forbidden")
        self.generic_visit(node)


def ensure_database():
    if not DB_PATH.exists():
        raise RuntimeError("groundwater_data.db not found. Run `python init_db.py` before deployment.")


def connect_db():
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def extract_python_block(text):
    match = re.search(r"```python\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return textwrap.dedent(match.group(1)).strip()


def validate_code(code):
    tree = ast.parse(code)
    SafetyVisitor().visit(tree)


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0:
        raise ImportError("Relative imports are not allowed")
    if name not in ALLOWED_IMPORTS:
        raise ImportError(f"Import not allowed: {name}")
    return __import__(name, globals, locals, fromlist, level)


def execute_generated_code(code):
    validate_code(code)

    job_id = uuid.uuid4().hex
    chart_path = STATIC_DIR / f"chart_{job_id}.png"
    report_path = STATIC_DIR / f"report_{job_id}.pdf"

    stdout = io.StringIO()
    safe_globals = {
        "__builtins__": {
            "__import__": safe_import,
            "len": len,
            "range": range,
            "min": min,
            "max": max,
            "sum": sum,
            "round": round,
            "sorted": sorted,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "str": str,
            "int": int,
            "float": float,
            "print": print,
        },
        "connect_db": connect_db,
        "sqlite3": sqlite3,
        "pd": pd,
        "plt": plt,
        "sns": sns,
        "canvas": canvas,
        "letter": letter,
        "CHART_PATH": str(chart_path),
        "REPORT_PATH": str(report_path),
    }

    plt.close("all")
    with redirect_stdout(stdout):
        exec(code, safe_globals, {})
    plt.close("all")

    assets = {}
    if chart_path.exists():
        assets["chartUrl"] = f"/static/{chart_path.name}"
        assets["chartBase64"] = base64.b64encode(chart_path.read_bytes()).decode("ascii")
    if report_path.exists():
        assets["pdfUrl"] = f"/static/{report_path.name}"
        assets["pdfBase64"] = base64.b64encode(report_path.read_bytes()).decode("ascii")

    return stdout.getvalue().strip(), assets


def call_groq(message):
    if client is None:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        max_tokens=1300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
    )
    return response.choices[0].message.content or ""


def fallback_answer(message):
    q = message.lower()
    with connect_db() as conn:
        if "karnataka" in q:
            df = pd.read_sql_query("""
                SELECT district_name, stage_extraction_percentage, status_category
                FROM district_assessments
                WHERE lower(state_name) = 'karnataka'
                ORDER BY stage_extraction_percentage DESC
            """, conn)
            lines = ["### Karnataka Groundwater Extraction"]
            for row in df.to_dict("records"):
                lines.append(
                    f"- {row['district_name']}: {row['stage_extraction_percentage']:.1f}% "
                    f"({row['status_category']})"
                )
            return "\n".join(lines)

        df = pd.read_sql_query("""
            SELECT state_name, district_name, stage_extraction_percentage, status_category
            FROM district_assessments
            ORDER BY stage_extraction_percentage DESC
            LIMIT 6
        """, conn)
        lines = ["### Highest Groundwater Stress Districts"]
        for row in df.to_dict("records"):
            lines.append(
                f"- {row['district_name']}, {row['state_name']}: "
                f"{row['stage_extraction_percentage']:.1f}% ({row['status_category']})"
            )
        return "\n".join(lines)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "online",
        "database": DB_PATH.exists(),
        "model": GROQ_MODEL,
        "groqConfigured": bool(GROQ_API_KEY),
    })


@app.post("/api/chat")
def chat():
    try:
        ensure_database()
        payload = request.get_json(force=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        llm_text = call_groq(message)
        code = extract_python_block(llm_text)

        if code:
            text, assets = execute_generated_code(code)
            return jsonify({
                "text": text or "Generated asset successfully.",
                "assetGenerated": bool(assets),
                **assets,
            })

        return jsonify({
            "text": llm_text.strip(),
            "assetGenerated": False,
        })

    except Exception as exc:
        if "GROQ_API_KEY is not configured" not in str(exc):
            traceback.print_exc()
        return jsonify({
            "text": fallback_answer(request.json.get("message", "") if request.is_json else ""),
            "assetGenerated": False,
            "warning": str(exc),
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
