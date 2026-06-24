param(
    [Parameter(Mandatory = $true)] [string]$RepoOwner,
    [Parameter(Mandatory = $true)] [string]$RepoName,
    [Parameter(Mandatory = $true)] [string]$TagName,
    [Parameter(Mandatory = $true)] [string]$Pat,
    [Parameter(Mandatory = $true)] [string[]]$FilesToUpload
)

function Invoke-GitHubAPI {
    param($Method, $Url, $Body = $null)
    $headers = @{ Authorization = "token $Pat"; "User-Agent" = "$RepoOwner-$RepoName-uploader" }
    if ($Body -ne $null) {
        $json = $Body | ConvertTo-Json -Depth 10
        return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers -ContentType 'application/json' -Body $json
    }
    else {
        return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers
    }
}

# 1) Create Release
$createUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/releases"
$body = @{ tag_name = $TagName; name = $TagName; body = "Release $TagName - upload automatique"; draft = $false; prerelease = $false }
try {
    $release = Invoke-GitHubAPI -Method Post -Url $createUrl -Body $body
}
catch {
    Write-Error "Erreur création release: $_"
    exit 1
}

$uploadUrlTemplate = $release.upload_url -replace '\{.*\}$', ''

# 2) Upload assets
foreach ($file in $FilesToUpload) {
    if (-Not (Test-Path $file)) { Write-Warning "Fichier introuvable : $file"; continue }
    $fileName = [System.IO.Path]::GetFileName($file)
    $mime = 'application/octet-stream'
    $uploadUrl = "$uploadUrlTemplate?name=$fileName"
    Write-Output "Uploading $fileName ..."
    try {
        $bytes = [System.IO.File]::ReadAllBytes($file)
        $headers = @{ Authorization = "token $Pat"; "User-Agent" = "$RepoOwner-$RepoName-uploader" }
        Invoke-RestMethod -Method Post -Uri $uploadUrl -Headers $headers -ContentType $mime -Body $bytes
        Write-Output "Uploaded: $fileName"
    }
    catch {
        Write-Error "Erreur upload $fileName: $_"
    }
}

Write-Output "Upload terminé. Release: $($release.html_url)"

# 3) Remove large files from repo and add instructions for Git LFS or Releases
Write-Output "\nÉtape optionnelle: retirer les binaires du dépôt et committer une .gitattributes pour Git LFS."
Write-Output "Fichiers considérés pour suppression :"
$FilesToUpload | ForEach-Object { Write-Output " - $_" }
Write-Output "\nSi vous confirmez, exécutez manuellement :"
Write-Output "git rm --cached path/to/largefile && git commit -m 'chore(release): remove large binaries, use GitHub Releases' && git push origin feature/online-mode"

# End
Write-Output "Script terminé."