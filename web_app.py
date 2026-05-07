from __future__ import annotations

import json
import importlib
import mimetypes
import os
import tempfile
import threading
import urllib.parse
import webbrowser
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app import (
    ALL_FIELDS,
    BUSINESS_FIELDS,
    FIELD_GROUPS,
    FIXED_BUSINESS_CONTACT,
    OCRPipeline,
    OCR_MODES,
    build_credit_scrub,
    extract_details_from_text,
    format_ein,
    provider_name,
)


HOST = "127.0.0.1"
PORT = int(os.getenv("OCR_WEB_PORT", "8765"))


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hand Writing Credit App</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #657283;
      --line: #d9dee7;
      --accent: #0f766e;
      --accent-2: #1d4ed8;
      --warn: #b45309;
      --shadow: 0 18px 48px rgba(25, 35, 55, 0.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, textarea, select { font: inherit; }
    .shell { width: min(1560px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 36px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 22px; }
    h1 { margin: 0; font-size: clamp(24px, 3vw, 36px); line-height: 1.08; letter-spacing: 0; }
    .subtle { margin: 7px 0 0; color: var(--muted); font-size: 14px; }
    .status {
      min-width: 250px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 8px;
      background: var(--panel); color: var(--muted); font-size: 13px; text-align: right;
      box-shadow: 0 8px 20px rgba(25, 35, 55, 0.06);
    }
    main { display: grid; grid-template-columns: minmax(300px, 360px) minmax(0, 1fr); gap: 18px; align-items: start; }
    .scrub-column { display: grid; gap: 18px; position: sticky; top: 20px; align-self: start; }
    .extractor-column { display: grid; grid-template-columns: minmax(280px, 320px) minmax(0, 1fr); gap: 18px; align-items: start; min-width: 0; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); }
    .upload-panel, .scrub-panel, .section { padding: 18px; }
    .upload-panel { position: sticky; top: 20px; }
    .dropzone {
      display: grid; place-items: center; min-height: 210px; border: 2px dashed #a8b2c1; border-radius: 8px;
      background: #fbfcfe; text-align: center; cursor: pointer; transition: border-color 160ms ease, background 160ms ease;
    }
    .dropzone.dragging { border-color: var(--accent); background: #ecfdf5; }
    .dropzone input { position: absolute; inline-size: 1px; block-size: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .drop-mark {
      width: 52px; height: 52px; margin: 0 auto 14px; border-radius: 8px; display: grid; place-items: center;
      background: #e7f4f2; color: var(--accent); font-weight: 800; font-size: 24px;
    }
    .drop-title { margin: 0; font-size: 16px; font-weight: 750; }
    .drop-copy { margin: 8px 0 0; color: var(--muted); font-size: 13px; line-height: 1.45; overflow-wrap: anywhere; }
    .actions { display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 16px; }
    .btn {
      min-height: 42px; border: 0; border-radius: 8px; padding: 10px 14px; color: #fff;
      background: var(--accent); font-weight: 750; cursor: pointer;
    }
    .btn.secondary { background: var(--accent-2); }
    .btn.ghost { background: #eef2f7; color: var(--ink); }
    .btn:disabled { cursor: not-allowed; opacity: 0.55; }
    .engine { width: 100%; min-height: 38px; border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fff; }
    .meta { display: grid; gap: 8px; margin-top: 16px; color: var(--muted); font-size: 13px; line-height: 1.45; }
    .content { display: grid; gap: 18px; min-width: 0; }
    .section-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 14px; }
    h2 { margin: 0; font-size: 17px; letter-spacing: 0; }
    .confidence { color: var(--muted); font-size: 12px; white-space: nowrap; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    label.field { display: grid; gap: 6px; min-width: 0; }
    .field span { color: #344055; font-size: 12px; font-weight: 750; }
    .field input {
      width: 100%; min-height: 40px; border: 1px solid var(--line); border-radius: 8px; padding: 9px 10px;
      color: var(--ink); background: #fff; outline: none;
    }
    .field input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.13); }
    textarea {
      width: 100%; min-height: 240px; resize: vertical; border: 1px solid var(--line); border-radius: 8px;
      padding: 12px; color: #263245; background: #fbfcfe; line-height: 1.45; outline: none;
    }
    .scrub-textarea { min-height: 230px; font-family: Consolas, "SFMono-Regular", monospace; font-size: 13px; }
    .scrub-output {
      width: 100%; min-height: 420px; border: 1px solid var(--line); border-radius: 8px; padding: 14px;
      background: #fff; color: var(--ink); font-size: 14px; line-height: 1.45; outline: none; overflow: auto; user-select: text;
      white-space: pre-wrap;
    }
    .scrub-output a {
      color: #1a0dab;
      text-decoration: underline;
    }
    .mini-btn {
      min-height: 32px; border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px;
      background: #eef2f7; color: var(--ink); font-size: 12px; font-weight: 750; cursor: pointer;
    }
    progress { width: 100%; height: 10px; accent-color: var(--accent); }
    .progress-wrap { display: none; margin-top: 14px; gap: 8px; }
    .progress-wrap.active { display: grid; }
    .warn { color: var(--warn); font-size: 13px; line-height: 1.45; }
    .raw-panel { display: none; }
    .raw-panel.active { display: block; }
    @media (max-width: 1180px) { main { grid-template-columns: 1fr; } .scrub-column, .upload-panel { position: static; } }
    @media (max-width: 860px) {
      header { display: grid; } .status { text-align: left; min-width: 0; } .extractor-column { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>D ANALYTICAL CREDIT FORM</h1>
        <p class="subtle">Upload a PDF or image to extract the required business and owner details.</p>
      </div>
      <div class="status" id="status">Ready</div>
    </header>
    <main>
      <aside class="scrub-column">
        <section class="panel scrub-panel">
          <div class="section-head"><h2>Pricing Scrub</h2></div>
          <textarea class="scrub-textarea" id="pricingScrub" spellcheck="false"></textarea>
        </section>
        <section class="panel scrub-panel">
          <div class="section-head">
            <h2>Credit Scrub</h2>
            <button class="mini-btn" id="copyCreditBtn" type="button">Copy</button>
          </div>
          <div class="scrub-output" id="creditScrub" tabindex="0"></div>
        </section>
      </aside>
      <section class="extractor-column">
        <aside class="panel upload-panel">
          <label class="dropzone" id="dropzone">
            <input id="fileInput" type="file" accept="application/pdf,image/*">
            <div>
              <div class="drop-mark">+</div>
              <p class="drop-title">select PDF / Image</p>
              <p class="drop-copy" id="fileName">Drag-drop & select your file</p>
            </div>
          </label>
          <div style="margin-top:12px">
            <select class="engine" id="engine">
              __OCR_MODE_OPTIONS__
            </select>
          </div>
          <div class="progress-wrap" id="progressWrap">
            <progress id="progress" value="0" max="100"></progress>
            <div class="subtle" id="progressText">Processing...</div>
          </div>
          <div class="actions">
            <button class="btn" id="extractBtn" disabled>Extract Details</button>
            <button class="btn secondary" id="submitCreditBtn" disabled>Submit</button>
            <button class="btn secondary" id="downloadBtn" disabled>Download Excel</button>
            <button class="btn ghost" id="clearBtn">Clear</button>
          </div>
          <div class="meta">
            <div>For best results, use a clear, straight, high-resolution scan or image.</div>
            <div class="warn">Please verify TIN and SSN values before downloading the Excel file.</div>
          </div>
        </aside>
        <section class="content" id="content"></section>
      </section>
    </main>
  </div>
  <script>
    const fieldGroups = __FIELD_GROUPS__;
    const fixedBusinessContact = __FIXED_CONTACT__;
    const state = { file: null, values: {} };
    fieldGroups.flatMap(g => g.fields).forEach(([key]) => state.values[key] = "");
    Object.assign(state.values, fixedBusinessContact);

    const $ = (id) => document.getElementById(id);
    const statusEl = $("status");
    const fileInput = $("fileInput");
    const fileName = $("fileName");
    const extractBtn = $("extractBtn");
    const downloadBtn = $("downloadBtn");
    const submitCreditBtn = $("submitCreditBtn");
    const clearBtn = $("clearBtn");
    const pricingScrub = $("pricingScrub");
    const creditScrub = $("creditScrub");
    const progressWrap = $("progressWrap");
    const progress = $("progress");
    const progressText = $("progressText");

    function setStatus(text) { statusEl.textContent = text; }
    function setProgress(active, value = 0, text = "Processing...") {
      progressWrap.classList.toggle("active", active);
      progress.value = value;
      progressText.textContent = text;
    }
    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }
    function renderFields() {
      Object.assign(state.values, fixedBusinessContact);
      const content = $("content");
      content.innerHTML = "";
      fieldGroups.forEach(group => {
        const panel = document.createElement("div");
        panel.className = "panel section";
        const found = group.fields.filter(([key]) => state.values[key]).length;
        panel.innerHTML = `<div class="section-head"><h2>${escapeHtml(group.name)}</h2><div class="confidence">${found} fields found</div></div><div class="grid"></div>`;
        const grid = panel.querySelector(".grid");
        group.fields.forEach(([key, label]) => {
          const field = document.createElement("label");
          field.className = "field";
          const locked = Object.prototype.hasOwnProperty.call(fixedBusinessContact, key);
          field.innerHTML = `<span>${escapeHtml(label)}</span><input data-key="${key}" autocomplete="off" value="${escapeHtml(state.values[key] || "")}" ${locked ? "readonly" : ""}>`;
          field.querySelector("input").addEventListener("input", event => {
            if (locked) {
              state.values[key] = fixedBusinessContact[key];
              event.target.value = fixedBusinessContact[key];
              return;
            }
            state.values[key] = event.target.value.trim();
            updateButtons();
            updateCreditScrub();
          });
          grid.appendChild(field);
        });
        content.appendChild(panel);
      });
      updateButtons();
      updateCreditScrub();
    }
    function previousMonthName() {
      const names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
      const now = new Date();
      return names[(now.getMonth() + 11) % 12];
    }
    function clean(value) { return String(value || "").replace(/\s+/g, " ").trim(); }
    function formatEin(value) {
      const digits = String(value || "").replace(/\D/g, "").slice(0, 9);
      return digits.length <= 2 ? digits : `${digits.slice(0, 2)}-${digits.slice(2)}`;
    }
    function normalizeMonth(value) {
      const aliases = { jan:"January", january:"January", feb:"February", february:"February", febuary:"February", mar:"March", march:"March", apr:"April", april:"April", may:"May", jun:"June", june:"June", jul:"July", july:"July", aug:"August", august:"August", sep:"September", sept:"September", september:"September", oct:"October", october:"October", nov:"November", november:"November", dec:"December", december:"December" };
      return aliases[String(value || "").toLowerCase().replace(/[^a-z]/g, "")] || "";
    }
    function parsePricing() {
      const text = pricingScrub.value.replace(/\r/g, "\n");
      const lines = text.split("\n").map(clean).filter(Boolean);
      let tier = lines[0] || "";
      tier = tier.split(/\bDeposits?(?:\s*\([^)]*\))?\s*:/i)[0].trim();
      if (/^(Deposits|Industry|TIB|State|Datamerch|Company\s+Website|Proceed)\b/i.test(tier)) tier = "";
      const read = (regex) => (text.match(regex) || ["", ""])[1].trim();
      const deposits = text.match(/\bDeposits?(?:\s*\(([^)]*)\))?\s*:\s*(.*?)(?:,\s*Industry\s*:|\n|\r|$)/i);
      const website = read(/Company\s+Website\s*:\s*([^\n\r]*)/i);
      return {
        tier,
        deposits: deposits ? clean(deposits[2]) : "",
        revenueMonth: normalizeMonth(deposits ? deposits[1] : "") || previousMonthName(),
        industry: read(/Industry\s*:\s*([^,\n\r]*)/i),
        tib: read(/\bTIB\s*:\s*([^,\n\r]*)/i),
        state: read(/\bState\s*:\s*([^,\n\r]*)/i),
        website: website && !/^not\s+found$/i.test(website) ? website : "Not Found"
      };
    }
    function googleItem(name, stateValue) {
      name = clean(name);
      if (!name) return "";
      const query = clean(`${name} ${stateValue || ""}`);
      return {
        text: `${query} Google Search`,
        href: `https://www.google.com/search?q=${encodeURIComponent(query)}`
      };
    }
    function updateCreditScrub() {
      const pricing = parsePricing();
      const scrubState = state.values.businessState || pricing.state || "";
      const lines = [];
      const html = [];
      const addLine = (line = "") => {
        lines.push(line);
        html.push(line ? `<div>${escapeHtml(line)}</div>` : "<br>");
      };
      const addLink = (item) => {
        lines.push(item.text);
        html.push(`<div><a href="${escapeHtml(item.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.text)}</a></div>`);
      };
      if (pricing.tier) {
        lines.push(pricing.tier, "");
        html.push(`<div>${escapeHtml(pricing.tier)}</div>`, "<br>");
      }
      const businessSearch = googleItem(state.values.businessName || state.values.businessDbaName, scrubState);
      const people = ["ownerName", "owner2Name", "owner3Name", "owner4Name"].map(k => googleItem(state.values[k], scrubState)).filter(Boolean);
      if (businessSearch) addLink(businessSearch);
      if (businessSearch && people.length) addLine("");
      people.forEach(addLink);
      if (businessSearch || people.length) addLine("");
      [
        `Company Website : ${pricing.website || "Not Found"}`, "", "FICO :",
        `${pricing.revenueMonth} Revenue : ${pricing.deposits}`,
        `Industry : ${pricing.industry}`, `TIB : ${pricing.tib}`, `State : ${scrubState}`,
        "Datamerch : No Match", "Received : N", `EIN : ${formatEin(state.values.einNumber)}`, "Customer Id :"
      ].forEach(addLine);
      const plainText = lines.join("\n").replace(/\n{3,}/g, "\n\n").trimEnd();
      creditScrub.dataset.plain = plainText;
      creditScrub.innerHTML = html.join("");
    }
    function updateButtons() {
      const found = Object.entries(state.values).some(([key, value]) => value && !["businessPhone", "businessEmail"].includes(key));
      extractBtn.disabled = !state.file;
      downloadBtn.disabled = !Object.values(state.values).some(Boolean);
      submitCreditBtn.disabled = !found;
    }
    function setFile(file) {
      state.file = file;
      fileName.textContent = file ? file.name : "Drag-drop & select your file";
      setStatus(file ? "File ready" : "Ready");
      updateButtons();
    }
    async function extractFile() {
      if (!state.file) return;
      setStatus("Uploading and OCR processing...");
      setProgress(true, 12, "Python OCR backend running...");
      extractBtn.disabled = true;
      const form = new FormData();
      form.append("file", state.file);
      form.append("engine", $("engine").value);
      try {
        const response = await fetch("/api/extract", { method: "POST", body: form });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Extraction failed");
        Object.assign(state.values, data.values || {});
        Object.assign(state.values, fixedBusinessContact);
        renderFields();
        setStatus(data.status || "Details extracted");
      } catch (error) {
        setStatus("Extraction failed");
        alert(error.message || error);
      } finally {
        setProgress(false);
        updateButtons();
      }
    }
    async function downloadExcel() {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: state.values })
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        alert(data.error || "Download failed");
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "business-owner-details.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    }
    function clearAll() {
      state.file = null;
      fieldGroups.flatMap(g => g.fields).forEach(([key]) => state.values[key] = "");
      Object.assign(state.values, fixedBusinessContact);
      fileInput.value = "";
      pricingScrub.value = "";
      setFile(null);
      renderFields();
    }
    fileInput.addEventListener("change", event => setFile(event.target.files[0] || null));
    extractBtn.addEventListener("click", extractFile);
    downloadBtn.addEventListener("click", downloadExcel);
    clearBtn.addEventListener("click", clearAll);
    pricingScrub.addEventListener("input", updateCreditScrub);
    $("copyCreditBtn").addEventListener("click", async () => {
      await navigator.clipboard.writeText(creditScrub.dataset.plain || creditScrub.textContent);
      setStatus("Credit scrub copied");
    });
    ["dragenter", "dragover"].forEach(name => $("dropzone").addEventListener(name, event => {
      event.preventDefault();
      $("dropzone").classList.add("dragging");
    }));
    ["dragleave", "drop"].forEach(name => $("dropzone").addEventListener(name, event => {
      event.preventDefault();
      $("dropzone").classList.remove("dragging");
    }));
    $("dropzone").addEventListener("drop", event => {
      const file = event.dataTransfer.files[0];
      if (file) setFile(file);
    });
    renderFields();
  </script>
</body>
</html>
"""


def html_page() -> bytes:
    groups = [{"name": name, "fields": fields} for name, fields in FIELD_GROUPS]
    mode_options = "\n".join(f"<option>{mode}</option>" for mode in OCR_MODES)
    page = (
        HTML
        .replace("__FIELD_GROUPS__", json.dumps(groups))
        .replace("__FIXED_CONTACT__", json.dumps(FIXED_BUSINESS_CONTACT))
        .replace("__OCR_MODE_OPTIONS__", mode_options)
    )
    return page.encode("utf-8")


def parse_multipart(content_type: str, body: bytes) -> dict[str, tuple[str, bytes] | str]:
    headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(headers + body)
    fields: dict[str, tuple[str, bytes] | str] = {}
    if not message.is_multipart():
        return fields
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if "form-data" not in disposition:
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_param("filename", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        if filename:
            fields[str(name)] = (str(filename), payload)
        elif name:
            fields[str(name)] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields


def export_rows(values: dict[str, str]) -> list[list[str]]:
    values = {**values, **FIXED_BUSINESS_CONTACT}
    return [
        ["Business Legal Name", values.get("businessName", ""), "", "", ""],
        ["Business DBA Name", values.get("businessDbaName", ""), "", "", ""],
        ["Business Address", values.get("businessAddress", ""), "", "", ""],
        ["Business State", values.get("businessState", ""), "", "", ""],
        ["Business City", values.get("businessCity", ""), "", "", ""],
        ["Business Zip", values.get("businessZip", ""), "", "", ""],
        ["Business Phone Number", values.get("businessPhone", ""), "", "", ""],
        ["Business Gmail", values.get("businessEmail", ""), "", "", ""],
        ["Tax ID (TIN #)", format_ein(values.get("einNumber", "")), "", "", ""],
        ["Owner Name", values.get("ownerName", ""), values.get("owner2Name", ""), values.get("owner3Name", ""), values.get("owner4Name", "")],
        ["Owner DOB", values.get("ownerDob", ""), values.get("owner2Dob", ""), values.get("owner3Dob", ""), values.get("owner4Dob", "")],
        ["Home Address", values.get("ownerAddress", ""), values.get("owner2Address", ""), values.get("owner3Address", ""), values.get("owner4Address", "")],
        ["Owner State", values.get("ownerState", ""), values.get("owner2State", ""), values.get("owner3State", ""), values.get("owner4State", "")],
        ["Owner City", values.get("ownerCity", ""), values.get("owner2City", ""), values.get("owner3City", ""), values.get("owner4City", "")],
        ["Owner Zip", values.get("ownerZip", ""), values.get("owner2Zip", ""), values.get("owner3Zip", ""), values.get("owner4Zip", "")],
        ["SSN#", values.get("ssn", ""), values.get("owner2Ssn", ""), values.get("owner3Ssn", ""), values.get("owner4Ssn", "")],
    ]


def build_xlsx(values: dict[str, str]) -> bytes:
    openpyxl = importlib.import_module("openpyxl")
    openpyxl_styles = importlib.import_module("openpyxl.styles")

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Extracted Details"
    for row in export_rows(values):
        sheet.append(row)
    thin = openpyxl_styles.Side(style="thin", color="D9DEE7")
    for row in sheet.iter_rows():
        for index, cell in enumerate(row, start=1):
            cell.alignment = openpyxl_styles.Alignment(horizontal="left", vertical="center", wrap_text=True)
            cell.border = openpyxl_styles.Border(top=thin, bottom=thin, left=thin, right=thin)
            if index == 1:
                cell.font = openpyxl_styles.Font(bold=True)
    for column, width in zip("ABCDE", [28, 36, 36, 36, 36]):
        sheet.column_dimensions[column].width = width
    fd, temp_name = tempfile.mkstemp(prefix="credit_export_", suffix=".xlsx")
    os.close(fd)
    temp = Path(temp_name)
    try:
        workbook.save(temp)
        return temp.read_bytes()
    finally:
        temp.unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "CreditOCRHTTP/1.0"

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_bytes(self, content: bytes, status: int = 200, content_type: str = "text/plain; charset=utf-8", extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: dict, status: int = 200) -> None:
        self.send_bytes(json.dumps(data).encode("utf-8"), status, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self.send_bytes(html_page(), content_type="text/html; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/extract":
                self.handle_extract()
            elif path == "/api/export":
                self.handle_export()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def handle_extract(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_multipart(content_type, self.rfile.read(length))
        upload = fields.get("file")
        if not isinstance(upload, tuple):
            self.send_json({"error": "File upload missing."}, 400)
            return
        filename, payload = upload
        engine = fields.get("engine", "Image")
        suffix = Path(filename).suffix or mimetypes.guess_extension(self.headers.get("Content-Type", "")) or ".bin"
        fd, temp_name = tempfile.mkstemp(prefix="ocr_upload_", suffix=suffix)
        os.close(fd)
        temp_path = Path(temp_name)
        temp_path.write_bytes(payload)
        progress_messages: list[str] = []
        pipeline = OCRPipeline(progress_messages.append)
        try:
            raw_text = pipeline.run(temp_path, str(engine))
            extracted = extract_details_from_text(raw_text)
            scrub = build_credit_scrub(extracted.values, "")
            self.send_json({
                "values": extracted.values,
                "rawText": raw_text,
                "creditScrub": scrub,
                "status": f"{provider_name(raw_text)} details extracted",
                "progress": progress_messages,
            })
        finally:
            pipeline.cleanup()
            temp_path.unlink(missing_ok=True)

    def handle_export(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        values = {**(payload.get("values") or {}), **FIXED_BUSINESS_CONTACT}
        content = build_xlsx(values)
        self.send_bytes(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            extra_headers={"Content-Disposition": 'attachment; filename="business-owner-details.xlsx"'},
        )


def run_server(open_browser: bool = True) -> None:
    url = f"http://{HOST}:{PORT}/"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Running on {url}", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    run_server(os.getenv("OCR_WEB_OPEN", "0") == "1")
