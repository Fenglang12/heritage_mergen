# 在本机 PowerShell / Cursor 终端中运行（不要在受限沙箱里跑）
Set-Location $PSScriptRoot\..
Write-Host "当前分支:" (git branch --show-current)
Write-Host "待推送提交:" (git log origin/main..HEAD --oneline 2>$null)
git push origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host "推送成功: https://github.com/guo276689-star/heritage_mergen" -ForegroundColor Green
} else {
    Write-Host "推送失败。若在国内网络，可尝试开 VPN 或配置代理后重试:" -ForegroundColor Yellow
    Write-Host '  git config --global http.proxy http://127.0.0.1:7890'
    Write-Host '  git config --global https.proxy http://127.0.0.1:7890'
}
