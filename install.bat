taskkill /F /IM python.exe
chcp 866
set root=C:\Users\Fastems\Anaconda3\
call %root%\Scripts\activate.bat %root%
call pip install .\textron-dev\
@echo off
pause
