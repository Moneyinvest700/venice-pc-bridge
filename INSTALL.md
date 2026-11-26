# venice-pc-bridge

Helper files for letting Venice AI (its normal chat, via the Web Scrape tool) see and control one Windows PC.
No secrets are stored here. The token is read at runtime from the local `venice_agent.py` on the PC.

Files
- `venice_agent2.py`: token-protected local web service (port 8798). Every URL it serves returns plain text.
  - `/look` returns the active window and the text on screen (Windows OCR) with click coordinates.
  - `/do?click=x,y&type=text&key=enter&open=https://...&scroll=-5&wait=2` does the action, then returns what is on screen.
  - `/do?steps=click=640,60;type=youtube.com;key=enter;wait=2` runs many actions in one fetch (saves Venice's daily scrape quota).
- `ocr.ps1`: Windows built-in OCR helper used by `/look`.

Install on the PC (PowerShell)
```
cd C:\pcagent
iwr https://raw.githubusercontent.com/Moneyinvest700/venice-pc-bridge/main/venice_agent2.py -OutFile venice_agent2.py
iwr https://raw.githubusercontent.com/Moneyinvest700/venice-pc-bridge/main/ocr.ps1 -OutFile ocr.ps1
Start-Process python -ArgumentList venice_agent2.py -WindowStyle Minimized -WorkingDirectory C:\pcagent
```
Needs Python with `pyautogui` and a tunnel (for example cloudflared) pointing at 127.0.0.1:8798.
Anyone with the full link can control the PC, so keep the link private.
