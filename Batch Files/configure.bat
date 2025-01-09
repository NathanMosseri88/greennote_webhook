@echo off

pip install virtualenv

cd /d "C:\Users\%USERNAME%\Desktop\New Projects\Greennote\Greennote_webhook"
python -m virtualenv venv

cd venv/scripts
call activate.bat

cd /d "C:\Users\%USERNAME%\Desktop\New Projects\Greennote\Greennote_webhook
pip install -r requirements.txt

cmd /k