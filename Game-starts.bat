@echo off
title 启动所有API服务
:: 使用脚本所在目录作为工作目录
cd %~dp0

echo 正在启动第一个API服务...
:: 启动第一个API
start cmd /k "cd NapCat.Shell && launcher.bat"
timeout /t 2 /nobreak >nul

echo 正在启动第二个API服务...
:: 启动第二个API
start cmd /k "call activate MaiBotEnv && cd MaiBot && python bot.py"
timeout /t 1 /nobreak >nul

echo 正在启动第三个API服务...
:: 启动第三个API (BERT)
start cmd /k "call activate MaiBotEnv && cd MaiBot-Napcat-Adapter && python main.py"
timeout /t 1 /nobreak >nul

echo 所有API服务已启动!
