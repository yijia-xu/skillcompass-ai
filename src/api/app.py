from io import BytesIO
import os
from pathlib import Path
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pypdf import PdfReader
from pydantic import BaseModel

from src.services.formatters import result_to_markdown

app = FastAPI(title="SkillCompass AI API", version="0.1.0")

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SkillCompass AI</title>
  <style>
    :root {
      --bg: #0b1016;
      --bg-2: #0f1722;
      --panel: rgba(17, 26, 36, 0.88);
      --text: #e6eef7;
      --muted: #9fb0c3;
      --accent: #2dce8f;
      --accent-2: #53ddb3;
      --border: rgba(45, 206, 143, 0.24);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      min-height: 100vh;
      background:
        radial-gradient(70% 55% at 50% -10%, rgba(45, 206, 143, 0.18), transparent 65%),
        linear-gradient(180deg, var(--bg-2) 0%, var(--bg) 100%);
      overflow-x: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(45, 206, 143, 0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(45, 206, 143, 0.05) 1px, transparent 1px);
      background-size: 56px 56px;
      mask-image: radial-gradient(circle at center, black 22%, transparent 78%);
      animation: drift 14s linear infinite;
    }
    .wrap { max-width: 1020px; margin: 0 auto; padding: 72px 24px 88px; position: relative; z-index: 1; }
    .top-nav {
      position: fixed;
      top: 16px;
      right: 18px;
      z-index: 2;
      display: flex;
      gap: 10px;
    }
    .top-nav a {
      color: #c9d7e6;
      text-decoration: none;
      border: 1px solid rgba(45, 206, 143, 0.3);
      background: rgba(17, 26, 36, 0.82);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      transition: .16s ease;
    }
    .top-nav a:hover {
      color: #eaf4ff;
      border-color: rgba(83, 221, 179, 0.6);
      box-shadow: 0 0 14px rgba(45, 206, 143, 0.2);
      transform: translateY(-1px);
    }
    .hero { text-align: center; margin-bottom: 38px; }
    .title {
      margin: 0;
      font-size: clamp(42px, 7vw, 68px);
      letter-spacing: -0.03em;
      font-weight: 700;
      line-height: 1.05;
    }
    .title span {
      display: inline-block;
      opacity: 0;
      transform: translateY(20px) scale(0.98);
      animation: title-in .9s cubic-bezier(.2,.8,.2,1) forwards;
      text-shadow: 0 0 20px rgba(45, 206, 143, 0.26);
    }
    .title .word1 { color: var(--text); animation-delay: .08s; }
    .title .word2 { color: var(--accent); animation-delay: .24s; margin-left: 8px; }
    .sub-primary {
      color: var(--muted);
      margin: 16px 0 0;
      font-size: 20px;
      font-weight: 500;
      opacity: 0;
      transform: translateY(8px);
      animation: fade-up .8s ease .4s forwards;
    }
    .sub-secondary {
      color: #93a8bd;
      margin: 10px 0 0;
      font-size: 15px;
      opacity: 0;
      transform: translateY(8px);
      animation: fade-up .8s ease .52s forwards;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 0 32px rgba(45, 206, 143, 0.11);
      padding: 22px;
      margin-bottom: 16px;
      opacity: 0;
      transform: translateY(10px);
      animation: fade-up .65s ease forwards;
    }
    .panel.p1 { animation-delay: .55s; }
    .panel.p2 { animation-delay: .68s; }
    .panel.result { animation-delay: .84s; }
    label { display: block; color: var(--muted); margin-bottom: 10px; font-size: 14px; }
    input[type="text"] {
      width: 100%;
      background: #0f1721;
      color: var(--text);
      border: 1px solid #224154;
      border-radius: 12px;
      padding: 14px 15px;
      font-size: 16px;
      outline: none;
      transition: border-color .18s ease, box-shadow .18s ease;
    }
    input:focus { border-color: rgba(83,221,179,.8); box-shadow: 0 0 0 4px rgba(45,206,143,.16); }
    .file-input-native {
      position: absolute;
      opacity: 0;
      pointer-events: none;
      width: 1px;
      height: 1px;
    }
    .file-input-shell {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      background: #0f1721;
      border: 1px solid #224154;
      border-radius: 12px;
      padding: 10px 12px;
      cursor: pointer;
      transition: border-color .18s ease, box-shadow .18s ease;
      min-height: 52px;
    }
    .file-input-shell:hover {
      border-color: rgba(83,221,179,.55);
    }
    .file-input-shell:focus-within {
      border-color: rgba(83,221,179,.8);
      box-shadow: 0 0 0 4px rgba(45,206,143,.16);
    }
    .file-cta {
      border: 1px solid rgba(83,221,179,.45);
      color: #c8f5e2;
      background: rgba(45,206,143,.12);
      padding: 8px 12px;
      border-radius: 10px;
      font-size: 14px;
      line-height: 1;
      white-space: nowrap;
    }
    .file-name {
      color: var(--muted);
      font-size: 15px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }
    button {
      width: 100%;
      border: none;
      border-radius: 12px;
      padding: 15px 18px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #082018;
      font-weight: 700;
      font-size: 17px;
      cursor: pointer;
      transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
      opacity: 0;
      transform: translateY(10px);
      animation: fade-up .65s ease .77s forwards;
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 0 22px rgba(45,206,143,.33); filter: saturate(1.06); }
    button:disabled { opacity: .55; cursor: not-allowed; box-shadow: none; transform: none; }
    .report-shell {
      background: #0f1721;
      border: 1px solid #213647;
      border-radius: 14px;
      padding: 20px 22px;
      min-height: 140px;
      color: #d4dfec;
      line-height: 1.55;
      font-size: 15px;
    }
    .md-report { max-width: 100%; overflow-x: auto; }
    .md-report h1 { font-size: 1.45rem; margin: 0 0 0.75rem; color: var(--text); font-weight: 700; letter-spacing: -0.02em; }
    .md-report h2 { font-size: 1.2rem; margin: 1.35rem 0 0.6rem; color: #c8e6d8; font-weight: 650; border-bottom: 1px solid #213647; padding-bottom: 0.35rem; }
    .md-report h3 { font-size: 1.05rem; margin: 1rem 0 0.45rem; color: var(--accent-2); font-weight: 600; }
    .md-report p { margin: 0.5rem 0; color: #c9d7e6; }
    .md-report ul, .md-report ol { margin: 0.45rem 0 0.65rem 1.25rem; padding: 0; color: #c9d7e6; }
    .md-report li { margin: 0.25rem 0; }
    .md-report a { color: var(--accent-2); text-decoration: underline; text-underline-offset: 3px; }
    .md-report a:hover { color: #7ae9c8; }
    .md-report code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.88em;
      background: rgba(45, 206, 143, 0.12);
      border: 1px solid rgba(45, 206, 143, 0.2);
      padding: 0.12em 0.4em;
      border-radius: 6px;
      color: #b8f0d8;
    }
    .md-report pre {
      margin: 0.65rem 0;
      padding: 14px 16px;
      background: #0a1018;
      border: 1px solid #1e3344;
      border-radius: 10px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .md-report pre code {
      background: none;
      border: none;
      padding: 0;
      color: #d0dde9;
      font-size: 0.86rem;
    }
    .md-report table {
      border-collapse: collapse;
      width: 100%;
      margin: 0.75rem 0;
      font-size: 0.92rem;
    }
    .md-report th, .md-report td {
      border: 1px solid #2a4054;
      padding: 8px 10px;
      text-align: left;
    }
    .md-report th { background: rgba(45, 206, 143, 0.1); color: #dff5ea; }
    .md-report tr:nth-child(even) td { background: rgba(15, 23, 33, 0.55); }
    .md-report blockquote {
      margin: 0.6rem 0;
      padding: 0.35rem 0 0.35rem 1rem;
      border-left: 3px solid var(--accent);
      color: #9fb5c8;
      background: rgba(45, 206, 143, 0.06);
      border-radius: 0 8px 8px 0;
    }
    .md-report hr { border: none; border-top: 1px solid #213647; margin: 1.25rem 0; }
    .md-report .md-placeholder, .md-report .md-error { color: var(--muted); margin: 0; }
    .md-report .md-error { color: #f0a8a8; }
    .status { color: var(--muted); font-size: 14px; min-height: 22px; margin-top: 8px; }
    .loader {
      display: none;
      margin-top: 10px;
      align-items: center;
      gap: 10px;
      color: #b9c8d9;
      font-size: 14px;
    }
    .loader.active { display: flex; }
    .loader-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 12px rgba(45,206,143,.55);
      animation: pulse-dot 1.1s ease-in-out infinite;
    }
    .loader-bar {
      position: relative;
      width: 160px;
      height: 6px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(45,206,143,.18);
    }
    .loader-bar::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, transparent 0%, rgba(83,221,179,.95) 45%, transparent 100%);
      transform: translateX(-100%);
      animation: scan 1.2s linear infinite;
    }
    @keyframes title-in {
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes fade-up {
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes drift {
      0% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
      100% { transform: translateY(0); }
    }
    @keyframes pulse-dot {
      0%, 100% { transform: scale(.9); opacity: .72; }
      50% { transform: scale(1.18); opacity: 1; }
    }
    @keyframes scan {
      from { transform: translateX(-100%); }
      to { transform: translateX(100%); }
    }
  </style>
</head>
<body>
  <nav class="top-nav">
    <a href="https://github.com/yijia-xu/gapsolver-ai" target="_blank" rel="noreferrer">GitHub</a>
    <a href="/docs" target="_blank" rel="noreferrer">API Docs</a>
  </nav>
  <div class="wrap">
    <div class="hero">
      <h1 class="title"><span class="word1">SkillCompass</span><span class="word2">AI</span></h1>
      <p class="sub-primary">Navigate your role skill gaps with live market signals.</p>
      <p class="sub-secondary">Upload resume · Analyze market gaps · Build your learning roadmap</p>
    </div>
    <form id="analyze-form">
      <div class="panel p1">
        <label for="target_role">Target Role</label>
        <input id="target_role" name="target_role" type="text" value="data engineer" />
      </div>
      <div class="panel p2">
        <label for="resume_file">Resume PDF</label>
        <label class="file-input-shell" for="resume_file">
          <span class="file-cta">Choose PDF</span>
          <span class="file-name" id="file-name">No file selected</span>
        </label>
        <input class="file-input-native" id="resume_file" name="resume_file" type="file" accept=".pdf" required />
      </div>
      <button id="submit-btn" type="submit">Analyze Skill Gaps</button>
      <div class="status" id="status"></div>
      <div class="loader" id="loader">
        <span class="loader-dot"></span>
        <span class="loader-bar"></span>
        <span id="loader-text">Scanning resume and market data...</span>
      </div>
    </form>
    <div class="result panel">
      <div class="report-shell">
        <div id="report" class="md-report"><p class="md-placeholder">Run analysis to see report…</p></div>
      </div>
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"></script>
  <script>
    const form = document.getElementById("analyze-form");
    const report = document.getElementById("report");
    const statusEl = document.getElementById("status");
    const submitBtn = document.getElementById("submit-btn");
    const fileNameEl = document.getElementById("file-name");
    const resumeFileInput = document.getElementById("resume_file");
    const loader = document.getElementById("loader");
    const loaderText = document.getElementById("loader-text");
    const defaultBtnLabel = submitBtn.textContent;
    resumeFileInput.addEventListener("change", () => {
      const file = resumeFileInput.files && resumeFileInput.files[0];
      fileNameEl.textContent = file ? file.name : "No file selected";
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!resumeFileInput.files.length) return;
      const fd = new FormData(form);
      submitBtn.disabled = true;
      submitBtn.textContent = "Analyzing...";
      statusEl.textContent = "Analyzing...";
      loader.classList.add("active");
      loaderText.textContent = "Scanning resume and market data...";
      report.innerHTML = "";
      try {
        const res = await fetch("/analyze-ui", { method: "POST", body: fd });
        loaderText.textContent = "Compiling your personalized report...";
        const raw = await res.text();
        let data = {};
        try {
          data = raw ? JSON.parse(raw) : {};
        } catch {
          const snippet = raw.replace(/\\s+/g, " ").trim().slice(0, 180);
          throw new Error(
            res.status + " " + (snippet || res.statusText || "Non-JSON response from server")
          );
        }
        if (!res.ok) {
          const detail = data.detail;
          const msg = Array.isArray(detail)
            ? detail.map((d) => d.msg || d).join("; ")
            : (detail || data.message || raw.slice(0, 300) || "Analysis failed");
          throw new Error(msg);
        }
        const md = data.markdown_report || "";
        const rawHtml = typeof marked !== "undefined" && marked.parse
          ? marked.parse(md, { breaks: true, gfm: true })
          : "<pre>" + md.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</pre>";
        report.innerHTML =
          typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(rawHtml) : rawHtml;
        statusEl.textContent = "Done.";
      } catch (err) {
        report.innerHTML = "";
        const p = document.createElement("p");
        p.className = "md-error";
        p.textContent = "Analyze failed: " + err.message;
        report.appendChild(p);
        statusEl.textContent = "Failed.";
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = defaultBtnLabel;
        loader.classList.remove("active");
      }
    });
  </script>
</body>
</html>
"""


class AnalyzeRequest(BaseModel):
    target_role: str
    resume_text: str
    resume_file_path: str = ""


class AnalyzeResponse(BaseModel):
    result: dict
    markdown_report: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.post("/analyze-ui")
def analyze_ui(target_role: str = Form(...), resume_file: UploadFile = File(...)) -> AnalyzeResponse:
    tmp_path: str | None = None
    try:
        content = resume_file.file.read()
        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Could not read PDF: {exc}",
            ) from exc
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Uploaded PDF has no extractable text (try a text-based PDF, not a scan).",
            )
        suffix = Path(resume_file.filename or "resume.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        from src.services.analyze import run_analysis

        try:
            result = run_analysis(target_role=target_role, resume_text=text, resume_file_path=tmp_path)
            markdown_report = result_to_markdown(result)
            return AnalyzeResponse(result=result.model_dump(), markdown_report=markdown_report)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc) or type(exc).__name__,
            ) from exc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    from src.services.analyze import run_analysis

    try:
        result = run_analysis(
            target_role=payload.target_role,
            resume_text=payload.resume_text,
            resume_file_path=payload.resume_file_path,
        )
        markdown_report = result_to_markdown(result)
        return AnalyzeResponse(result=result.model_dump(), markdown_report=markdown_report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc) or type(exc).__name__,
        ) from exc
