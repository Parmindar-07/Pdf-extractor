# Python OCR Credit App

## Index

1. Run
2. Frontend changes
3. Extraction fixes
4. OCR mode logic
5. Installed packages
6. Install notes / pending items
7. Files changed

## 1. Run

Browser / Google Chrome me chalane ke liye:

```powershell
python web_app.py
```

Open:

```text
http://127.0.0.1:8765/
```

Helper script:

```powershell
.\run_web_app.ps1
```

Desktop Tkinter version:

```powershell
python app.py
```

## 2. Frontend changes

Dropdown  Sirf 3 options hain:

- `Image`
- `Handwriting`
- `Text PDF`

Backend khud decide karta hai kaunsi OCR library use karni hai.

## 3. Extraction fixes

Parser ab `Label: Data` rule strictly follow karta hai:

- `Business Phone Number` aur `Business Gmail` hard-locked hain.
- Kisi bhi PDF/image/OCR output se phone/email import nahi hoga.
- Hamesha fixed values rahengi:
  - Phone: `6468459754`
  - Email: `contracts@tvtcapital.com`
- Browser UI me ye fields readonly hain.
- Export/Excel me bhi ye fixed values hi jayengi.

- `:` ke pehle wali line/phrase label maana jayega.
- `:` ke baad wali value data maana jayega.
- Same row me next `Label:` milte hi previous value stop ho jayegi.
- Empty labels, checkbox labels, legal-entity labels, annual-income labels, etc. ko business/owner fields me galat fill nahi karega.
- `First name:` + `Last name:` ko combine karke owner name banata hai.
- `State of Incorporation:` ko address state nahi banata.
- Broadway style labels add kiye: `Company Name`, `Doing Business As (DBA)`, `Physical Address (no PO Boxes)`, `SSI Number`, `Date of birth`, `Home address (no PO Boxes)`, etc.
- Fintek/Funding Application PDFs ke text-layer labels handle kiye: `Legal Company Name`, `DBA Name`, `EIN`, `Business Address`, `Full Name`, `Ownership Percent`, `SSN`, `Home Address`.
- Blank owner/business labels ab next label ya authorization paragraph ko data nahi maanenge.
- ZIP fields me sirf valid 5-digit ZIP accept hota hai.

Tested sample:

- `1777585764618_Fintek_Application_Secure_Car_Care_LLC.pdf`
- Extracted clean: `Secure Car Care LLC`, `11054 Ventura Blvd`, `Studio City CA 91604`, `45-4969724`, `Joseph Roberts`, `01/13/1983`, `225 south ardmore ave`, `90004`, `023644001`.

Jotform style sample:

- `20260505030042_jotform_application_6537592314117841285.pdf`
- Added support for multi-line address blocks like:
  - `Business Address:`
  - street line
  - `HAMDEN, Connecticut, 06514`
- Added `Business Owner:` mapping to owner name.
- Extracted clean: `A&Y GROUP INC`, `63 GLEMBY STREET`, `HAMDEN CT 06514`, `90-1119446`, `ETE ADOTE`, `10/05/1975`, `043965890`.

Broadway / TCPDF sequential-value sample:

- `gfddfgfd.pdf`
- This form stores labels first and values later after `ID: ... Signed: ...`.
- Added a layout-specific mapper for that value order.
- Extracted clean: `Else Nutrition USA Inc`, `501 W. Schrock Rd., Suite 107`, `Westerville OH 43081`, `38-4140626`, `Limor Seltzer`, `10/26/1972`, `229 W. Main St`, `New Albany OH 43054`, `078769305`.

Sapphire Capital sample:

- `Application_KIDWELL_HOME_AND_FENCE__LLC.pdf`
- Added `Legal Business Name:` support.
- Extracted clean: `KIDWELL HOME AND FENCE, LLC`, `102 LADYSMITH DRIVE`, `STEPHENS CITY VA 22655`, `93-1346876`, `JOSEPH KIDWELL`, `6/2/1969`, `214868883`.

BridgePoint / signed app sequential sample:

- `Signed App.pdf`
- This form also stores labels first and values later in a fixed order.
- Added a BridgePoint sequential mapper.
- Extracted clean: `Stevenson Hvac Inc`, `329 Indianapolis Rd`, `Mooresville IN 46158`, `99-2395840`, `Richard Stevenson`, `08/08/1977`, `342 Wakefield Trace`, `Greenwood IN 46142`, `525271058`.

Hand Writing Credit App table sample:

- `Hand_Writing_Credit_App.pdf`
- Added table parser for `Field / Value` rows.
- Extracted clean: `McMahons Steel Erections LLC`, `138 Dalton Circle`, `Hendersonville TN 37075`, `99-2438398`, `Zach McMahon`, `04/16/1984`, `288942607`.

Fast Funds / TCPDF sample:

- `7187-Application.pdf`
- Added mapper for Fast Funds sequential values after the consent/signature text.
- Extracted clean: `Brian Potkin`, `FFG`, `14011 Ventura Blvd STE 204`, `CA 91423`, `55-5337635`, `Brian Potkin`, `4488 White Pine Way`, `Oceanside CA 92057`, `555337635`.

ShopFunder next-line sample:

- `6538007685122693805 (1).pdf`
- Added next-line label parser for ShopFunder fields.
- Extracted clean: `A&Y Group INC`, `63 Glemby St`, `Hamden CT 06514`, `90-1119446`, `Ete Adote`, `10/05/1975`, `043965890`.

AIRS Capital sample:

- `AIRS CAPITAL App-2026 - Trinity Healthcare Supply LLC - ALTRX.pdf`
- Added AIRS sequential mapper.
- Extracted clean: `Trinity Healthcare Supply LLC`, `AltRX`, `3333 W Kennedy Blvd, Ste 207`, `Tampa FL 33609`, `86-3020397`, `Gurjotpal Batra`, `801 Bayshore Blvd`, `Tampa FL 33606`, `064805061`.

## 4. OCR mode logic

`Text PDF`:

- Pehle PDF text layer read karta hai.
- Agar text layer blank ho to OCR fallback try karta hai.

`Image`:

- OpenCV preprocessing.
- Tesseract, PaddleOCR, EasyOCR, DocTR ko best-effort order me try karta hai.

`Handwriting`:

- TrOCR, EasyOCR, Tesseract, PaddleOCR, DocTR ko best-effort order me try karta hai.

Missing library ki wajah se app full fail nahi hota; next available engine try karta hai.

## 5. Installed packages

Installed / verified:

- `pymupdf`
- `pillow`
- `opencv-python`
- `opencv-python-headless`
- `pytesseract`
- `openpyxl`
- `transformers`
- `torch`
- `torchvision`
- `python-doctr`
- `easyocr`
- `scikit-image`
- `lazy-loader`
- `imageio`
- `tifffile`
- `ninja`
- `python-bidi==0.4.2`

EasyOCR compatibility fix:

- Python 3.14 par latest `python-bidi` Rust build fail hua.
- `python-bidi==0.4.2` install kiya.
- Installed `bidi` package me `get_display` compatibility export add kiya, taaki EasyOCR import ho sake.

## 6. Install notes / pending items

Tesseract system binary:

- `pytesseract` Python package install ho gaya.
- Windows Tesseract binary install karne ke liye `winget install --id UB-Mannheim.TesseractOCR` try kiya.
- Installer download hua, par install step `operation was canceled by the user` se stop ho gaya.
- Code common Tesseract paths auto-detect karta hai. Agar manually install karoge to app use kar lega.
- Current sample jaise text PDFs ke liye Tesseract required nahi hai; `Text PDF` mode PyMuPDF se direct text read karta hai.

PaddleOCR:

- `paddlepaddle` ka Windows Python 3.14 wheel available nahi mila.
- App me PaddleOCR fallback code rakha hai, lekin current Python 3.14 setup me Paddle backend active nahi hai.

## 7. Files changed

- `app.py`: OCR backend, extraction parser, dropdown modes, dynamic optional imports.
- `web_app.py`: browser frontend + Python backend API.
- `requirements.txt`: installed/optional packages list.
- `run_web_app.ps1`: local browser server helper.
