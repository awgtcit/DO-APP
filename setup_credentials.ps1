# ============================================================
# PowerShell Credential Setup Script
# Run ONCE before starting the Flask application.
# Stores DB credentials as persistent user environment variables.
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Intranet Portal - Credential Setup"    -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Prompt for each value
$dbServer   = Read-Host "Enter DB Server (e.g. MTC-IIS\SQLEXPRESS)"
$dbName     = Read-Host "Enter Database Name (e.g. mtcintranet)"
$dbUser     = Read-Host "Enter DB Username"
$dbPassword = Read-Host "Enter DB Password" -AsSecureString

# Convert SecureString back to plain text for storage
$BSTR       = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPassword)
$dbPassText = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)

# Optional: LDAP and SMTP credentials
Write-Host ""
Write-Host "--- Optional: LDAP Configuration ---" -ForegroundColor Yellow
$ldapServer = Read-Host "Enter LDAP Server IP (leave blank to skip)"
$ldapPort   = Read-Host "Enter LDAP Port (default: 389)"
if ([string]::IsNullOrWhiteSpace($ldapPort)) { $ldapPort = "389" }

Write-Host ""
Write-Host "--- Optional: SMTP Configuration ---" -ForegroundColor Yellow
$smtpHost   = Read-Host "Enter SMTP Host (leave blank to skip)"
$smtpUser   = Read-Host "Enter SMTP Username (leave blank to skip)"
if (-not [string]::IsNullOrWhiteSpace($smtpUser)) {
    $smtpPass = Read-Host "Enter SMTP Password" -AsSecureString
    $BSTR2       = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($smtpPass)
    $smtpPassText = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR2)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR2)
}
$smtpPort   = Read-Host "Enter SMTP Port (default: 587)"
if ([string]::IsNullOrWhiteSpace($smtpPort)) { $smtpPort = "587" }

# Store as persistent User environment variables
[System.Environment]::SetEnvironmentVariable("DB_SERVER",   $dbServer,   "User")
[System.Environment]::SetEnvironmentVariable("DB_NAME",     $dbName,     "User")
[System.Environment]::SetEnvironmentVariable("DB_USER",     $dbUser,     "User")
[System.Environment]::SetEnvironmentVariable("DB_PASSWORD", $dbPassText, "User")

if (-not [string]::IsNullOrWhiteSpace($ldapServer)) {
    [System.Environment]::SetEnvironmentVariable("LDAP_SERVER", $ldapServer, "User")
    [System.Environment]::SetEnvironmentVariable("LDAP_PORT",   $ldapPort,   "User")
}

if (-not [string]::IsNullOrWhiteSpace($smtpHost)) {
    [System.Environment]::SetEnvironmentVariable("SMTP_HOST",     $smtpHost,       "User")
    [System.Environment]::SetEnvironmentVariable("SMTP_USER",     $smtpUser,       "User")
    [System.Environment]::SetEnvironmentVariable("SMTP_PASSWORD", $smtpPassText,   "User")
    [System.Environment]::SetEnvironmentVariable("SMTP_PORT",     $smtpPort,       "User")
}

# Also set in current session so Flask can use immediately
$env:DB_SERVER   = $dbServer
$env:DB_NAME     = $dbName
$env:DB_USER     = $dbUser
$env:DB_PASSWORD = $dbPassText

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Credentials saved successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Stored variables:" -ForegroundColor Gray
Write-Host "  DB_SERVER   = $dbServer" -ForegroundColor Gray
Write-Host "  DB_NAME     = $dbName" -ForegroundColor Gray
Write-Host "  DB_USER     = $dbUser" -ForegroundColor Gray
Write-Host "  DB_PASSWORD = ********" -ForegroundColor Gray

if (-not [string]::IsNullOrWhiteSpace($ldapServer)) {
    Write-Host "  LDAP_SERVER = $ldapServer" -ForegroundColor Gray
    Write-Host "  LDAP_PORT   = $ldapPort" -ForegroundColor Gray
}
if (-not [string]::IsNullOrWhiteSpace($smtpHost)) {
    Write-Host "  SMTP_HOST   = $smtpHost" -ForegroundColor Gray
    Write-Host "  SMTP_USER   = $smtpUser" -ForegroundColor Gray
    Write-Host "  SMTP_PORT   = $smtpPort" -ForegroundColor Gray
}

Write-Host ""
Write-Host "You can now start the Flask app with:" -ForegroundColor Cyan
Write-Host "  cd app" -ForegroundColor White
Write-Host "  python run.py" -ForegroundColor White
Write-Host ""
