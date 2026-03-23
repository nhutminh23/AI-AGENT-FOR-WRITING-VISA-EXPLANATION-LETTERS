## DS-160 Auto Config Generator

This app generates a set of **Tampermonkey** userscripts that automatically fill the **DS-160** web form for the applicant.

The app reads applicant data from files you place in the local `input/` folder (currently **DOCX** and **PDF**), uses an AI agent to convert that information into structured configuration data, and then injects the configuration into pre-defined DS-160 Tampermonkey script templates.

At the end, your generated scripts are saved into the `output/` folder and ready to be installed in Tampermonkey.

## What it does

1. **Input ingestion**
   - Scans the `input/` folder for supported files:
     - `*.docx`
     - `*.pdf`
   - Extracts the text content from each file.
   - Builds a single prompt context containing the content of all input files.

2. **AI-based extraction**
   - An AI agent uses the prompt template and a rules/notes file to map extracted text into the configuration needed by each DS-160 Tampermonkey step/script.

3. **Script generation**
   - The app merges the produced configuration into **18 DS-160 script templates**.
   - The filled scripts are written into `output/`.

4. **UI output**
   - The UI displays generated scripts with:
     - `Config (JSON)` tab
     - `Full Script` tab (default)
   - You can copy the full script code and paste it into Tampermonkey.

## UI language

The web interface supports **two languages**:

- **Vietnamese (VI)**: default
- **English (EN)**

Use the small flag buttons in the top-right corner to switch between languages.

## How to use (quick steps)

1. **Prepare your input data**
   - Place your DS-160 applicant information file(s) into:
     - `input/`
   - Supported formats:
     - DOCX (`.docx`)
     - PDF (`.pdf`)
   - Example:
     - `input/DS-160-of-Ms-Ngan.pdf`

2. **Run the app**
   - Start the backend server (FastAPI) and open the web UI.
   - The page will show a status message once it detects input files.

3. **Generate scripts**
   - Click **“Xử lý dữ liệu từ thư mục /input”** (or **“Process data from /input folder”**).
   - The app produces scripts and saves them into:
     - `output/`

4. **Install scripts into Tampermonkey**
   - Open the Tampermonkey dashboard.
   - Click **Create a new script…**
   - For each generated DS-160 step:
     - Copy the content from the app’s **`Full Script`** tab
     - Paste it into the Tampermonkey editor
     - Save
   - Ensure Tampermonkey is enabled.

5. **Run on DS-160**
   - Go to the DS-160 form page in your browser.
   - Run/trigger the scripts using the DS-160 workflow (Tampermonkey usually starts automatically when matching pages load).

## Repository structure (high level)

- `input/`
  - Your `.docx` and `.pdf` files containing the applicant information.
- `output/`
  - The generated and injected Tampermonkey scripts (and `configs.json` used internally).
- `frontend/`
  - The web UI (language toggle + generation results view).
- `script/`
  - Script templates (18 DS-160 step scripts).
- `notes.md`
  - Prompt/rules content used by the AI agent.

## Notes / limitations

- PDF text extraction quality depends on how the PDF was produced (scanned images vs. real text).
- If some fields are not extracted correctly, improve the input documents or adjust the rules/notes used by the AI agent.

