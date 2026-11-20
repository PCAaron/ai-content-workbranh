@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0" || exit /b 1
call docker compose version >nul 2>&1
if errorlevel 1 (
  echo 请先安装并启动 Docker Desktop，使用 Linux 容器，再双击本文件。
  goto failed
)
call docker compose up --build --wait -d
if errorlevel 1 goto failed
call docker compose exec web python manage.py first_reviewer
if errorlevel 1 goto failed
echo 工作台已就绪：http://127.0.0.1:8000/
if not defined CI start "" "http://127.0.0.1:8000/"
popd
exit /b 0

:failed
echo 启动未完成。请根据上方提示修正，再次双击 start.cmd。
if not defined CI pause
popd
exit /b 1
