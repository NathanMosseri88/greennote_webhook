@echo off
cd /d "C:\Users\kyf_achworks\Desktop\New Projects\Greennote\greennote_webhook>"

call venv\Scripts\activate

start "Flask App" cmd /k "python main.py"

start "ngrok Tunnel" cmd /k "C:\Users\kyf_achworks\Desktop\ngrok.exe http --domain=one-imp-mistakenly.ngrok-free.app 8080 -log=C:\Users\kyf_achworks\Desktop\ngrok.log"


