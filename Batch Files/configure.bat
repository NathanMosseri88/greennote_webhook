@echo off

C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\scripts\pip3 install virtualenv

cd /d "C:\Users\%USERNAME%\Desktop\New Projects\Greennote\Greennote_webhook"
C:\Users\kyf_achworks\AppData\Local\Programs\Python\Python312\python -m virtualenv venv

cd venv/scripts
call activate.bat

cd /d "C:\Users\%USERNAME%\Desktop\New Projects\Greennote\Greennote_webhook
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\scripts\pip3 install -r requirements.txt

cmd /k