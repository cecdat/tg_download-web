$versionFile = "version.txt"

# 1. 读取或初始化版本号
if (Test-Path $versionFile) {
    $version = Get-Content $versionFile
    # 假设版本号格式为 x.y.z
    $parts = $version.Split('.')
    if ($parts.Count -eq 3) {
        $parts[2] = [int]$parts[2] + 1
        $version = "$($parts[0]).$($parts[1]).$($parts[2])"
    } else {
        $version = "1.0.0"
    }
} else {
    $version = "1.0.0"
}

# 2. 保存新版本号
Set-Content -Path $versionFile -Value $version
Write-Host "📦 打包版本: $version"

# 3. 创建部署包 (包含版本号的文件名和通用文件名)
$timestamp = Get-Date -Format "yyyyMMdd_HHmm"
$zipName = "tg_downloader_v${version}.zip"
$prodZipName = "tg_downloader_production.zip"

$files = @(
    "tg-download-web.py",
    "telegram_downloader.py",
    "database.py",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "templates",
    "README.md",
    "deploy.sh",
    "version.txt"
)

# 移除旧文件
Remove-Item $zipName -ErrorAction SilentlyContinue
Remove-Item $prodZipName -ErrorAction SilentlyContinue

# 打包
Compress-Archive -Path $files -DestinationPath $prodZipName

# 复制一份带版本号的备份 (可选)
Copy-Item $prodZipName $zipName

Write-Host "✅ 打包完成!"
Write-Host "   - 生产包: $prodZipName"
Write-Host "   - 版本包: $zipName"
