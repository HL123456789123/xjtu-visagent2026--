$ErrorActionPreference = 'Stop'

# Runs the no-external-dependency acceptance round. Secrets are read only by
# Docker Compose from the local environment and are never handled by this file.
$project = 'visagent-history-dev'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Write-Utf8Json([string]$Path, $Value) {
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 10 -Compress), [Text.UTF8Encoding]::new($false))
}

function Invoke-Status([string[]]$Arguments) {
    $status = & curl.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "curl failed with exit code $LASTEXITCODE" }
    return $status
}

function Wait-HttpOk([string]$Url, [int]$Attempts = 45) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        $status = & curl.exe -s -o NUL -w '%{http_code}' $Url 2>$null
        if ($status -eq '200') { return }
        Start-Sleep -Seconds 2
    }
    throw "health check timed out: $Url"
}

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) { throw "$Message (expected $Expected, got $Actual)" }
}

function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Get-Json([string]$Path) { Get-Content -Raw -Encoding utf8 $Path | ConvertFrom-Json }

Push-Location $root
$work = $null
try {
    $env:FOOD_PROVIDER = 'mock'
    $env:LLM_MODE = 'fake'
    docker compose -p $project up -d --force-recreate backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'

    $suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
    $bytes = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $account = [ordered]@{
        username = "codexmock$suffix"
        email = "codexmock$suffix@example.com"
        password = [Convert]::ToBase64String($bytes).Replace('+', 'A').Replace('/', 'B').Replace('=', 'C')
    }
    $work = Join-Path $env:TEMP "visagent-mock-$suffix"
    New-Item -ItemType Directory -Path $work | Out-Null
    $accountPath = Join-Path $work 'account.json'
    Write-Utf8Json $accountPath $account

    $registerBody = Join-Path $work 'register.json'
    $registrationStatus = Invoke-Status @('-s', '-o', $registerBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/auth/register', '-H', 'Content-Type: application/json', '--data-binary', "@$accountPath")
    Assert-Equal $registrationStatus '201' 'mock validation account registration failed'
    $loginBody = Join-Path $work 'login.json'
    $loginStatus = Invoke-Status @('-s', '-o', $loginBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/auth/login', '-H', 'Content-Type: application/json', '--data-binary', "@$accountPath")
    Assert-Equal $loginStatus '200' 'mock validation account login failed'
    $token = (Get-Json $loginBody).access_token
    Assert-True $token 'mock validation login did not return a token'
    $auth = "Authorization: Bearer $token"

    $modelBody = Join-Path $work 'model.json'
    $modelStatus = Invoke-Status @('-s', '-o', $modelBody, '-w', '%{http_code}', 'http://127.0.0.1:8888/api/food/model-status', '-H', $auth)
    Assert-Equal $modelStatus '200' 'mock model status failed'
    $model = Get-Json $modelBody
    Assert-Equal $model.data.provider 'mock' 'model status did not identify mock provider'

    $imagePath = Join-Path $root 'frontend\public\food-carousel-1.jpg'
    $recognitionBody = Join-Path $work 'recognition.json'
    $recognitionStatus = Invoke-Status @('-s', '-o', $recognitionBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/food/recognitions', '-H', $auth, '-F', "images=@$imagePath;type=image/jpeg", '-F', "images=@$imagePath;type=image/jpeg", '-F', 'conf_threshold=0.25')
    Assert-Equal $recognitionStatus '201' 'mock multi-image recognition failed'
    $recognition = Get-Json $recognitionBody
    Assert-Equal $recognition.data.provider 'mock' 'recognition response did not identify mock provider'
    $imageIndexes = @($recognition.data.images | ForEach-Object { $_.image_index })
    Assert-Equal ($imageIndexes -join ',') '0,1' 'two-image upload did not preserve image indexes'
    $recognitionId = $recognition.data.recognition_id

    $confirmationPath = Join-Path $work 'confirmation.json'
    Write-Utf8Json $confirmationPath ([ordered]@{ ingredients = @(
        [ordered]@{ name = 'tomato'; class_name = $null; quantity = 2; unit = 'piece'; source = 'manual' },
        [ordered]@{ name = 'egg'; class_name = $null; quantity = 2; unit = 'piece'; source = 'manual' }
    ) })
    $confirmationBody = Join-Path $work 'confirmation-response.json'
    $confirmationStatus = Invoke-Status @('-s', '-o', $confirmationBody, '-w', '%{http_code}', '-X', 'PUT', "http://127.0.0.1:8888/api/food/recognitions/$recognitionId/ingredients", '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$confirmationPath")
    Assert-Equal $confirmationStatus '200' 'manual ingredient confirmation failed'
    $confirmedCount = (Get-Json $confirmationBody).data.confirmed_ingredients.Count
    Assert-Equal $confirmedCount 2 'manual confirmation did not retain two ingredients'

    $recipePath = Join-Path $work 'recipe.json'
    Write-Utf8Json $recipePath ([ordered]@{ recognition_id = $recognitionId; preferences = [ordered]@{ servings = 2; taste = 'home-style'; max_time_minutes = 45; avoid_ingredients = @() } })
    $recipeBody = Join-Path $work 'recipe-response.json'
    $recipeStatus = Invoke-Status @('-s', '-o', $recipeBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/recipes', '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$recipePath")
    Assert-Equal $recipeStatus '201' 'fake LLM recipe generation failed'
    $recipe = Get-Json $recipeBody
    Assert-Equal $recipe.data.version 1 'fake LLM recipe did not start at version 1'
    Assert-True $recipe.data.generator.is_mock 'fake validation did not identify fake LLM'
    Assert-True $recipe.data.nutrition_disclaimer 'recipe nutrition disclaimer was missing'
    $recipeId = $recipe.data.recipe_id

    $sessionPath = Join-Path $work 'session.json'
    Write-Utf8Json $sessionPath ([ordered]@{ recipe_id = $recipeId })
    $sessionBody = Join-Path $work 'session-response.json'
    $sessionStatus = Invoke-Status @('-s', '-o', $sessionBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/chat/sessions', '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$sessionPath")
    Assert-Equal $sessionStatus '201' 'mock chat session creation failed'
    $sessionId = (Get-Json $sessionBody).data.session_id
    $messagePath = Join-Path $work 'message.json'
    $updateMessage = ([string][char]0x6539) + ([char]0x6210) + ([char]0x4E09) + ([char]0x4EBA) + ([char]0x4EFD) + ([char]0x5E76) + ([char]0x4E14) + ([char]0x5C11) + ([char]0x653E) + ([char]0x6CB9)
    Write-Utf8Json $messagePath ([ordered]@{ content = $updateMessage })
    $ssePath = Join-Path $work 'chat-sse.txt'
    $sseStatus = Invoke-Status @('-sS', '-o', $ssePath, '-w', '%{http_code}', '-N', '-X', 'POST', "http://127.0.0.1:8888/api/chat/sessions/$sessionId/messages", '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$messagePath")
    Assert-Equal $sseStatus '200' 'fake LLM chat stream failed'
    $sse = Get-Content -Raw -Encoding utf8 $ssePath
    $hasToken = $sse -match '(?m)^event: token$'
    $hasRecipeUpdated = $sse -match '(?m)^event: recipe_updated$'
    $hasDone = $sse -match '(?m)^event: done$'
    $hasLegacyEvent = $sse -match '(?m)^event: (message|chunk|complete)$'
    Assert-True ($hasToken -and $hasRecipeUpdated -and $hasDone -and -not $hasLegacyEvent) 'fake chat stream events did not satisfy the V1 contract'

    $recipeAfterChatBody = Join-Path $work 'recipe-after-chat.json'
    $recipeAfterChatStatus = Invoke-Status @('-s', '-o', $recipeAfterChatBody, '-w', '%{http_code}', "http://127.0.0.1:8888/api/recipes/$recipeId", '-H', $auth)
    Assert-Equal $recipeAfterChatStatus '200' 'recipe fetch after fake chat failed'
    $recipeAfterChat = Get-Json $recipeAfterChatBody
    Assert-Equal $recipeAfterChat.data.version 2 'fake chat update did not persist version 2'

    $historyBody = Join-Path $work 'history.json'
    $historyStatus = Invoke-Status @('-s', '-o', $historyBody, '-w', '%{http_code}', 'http://127.0.0.1:8888/api/recipes/history?page=1&page_size=20', '-H', $auth)
    Assert-Equal $historyStatus '200' 'history fetch failed'
    $history = Get-Json $historyBody
    Assert-True ($history.data.total -ge 1) 'history did not contain the mock recipe'
    $dashboardBody = Join-Path $work 'dashboard.json'
    $dashboardStatus = Invoke-Status @('-s', '-o', $dashboardBody, '-w', '%{http_code}', 'http://127.0.0.1:8888/api/dashboard/food-stats', '-H', $auth)
    Assert-Equal $dashboardStatus '200' 'food dashboard fetch failed'
    $dashboard = Get-Json $dashboardBody
    Assert-True ($dashboard.data.overview.recipes -ge 1 -and $dashboard.data.overview.chat_sessions -ge 1) 'food dashboard did not aggregate mock data'
    $ordinaryAdminStatus = Invoke-Status @('-s', '-o', 'NUL', '-w', '%{http_code}', 'http://127.0.0.1:8888/api/admin/users', '-H', $auth)
    Assert-Equal $ordinaryAdminStatus '403' 'ordinary user admin API did not return 403'

    docker compose -p $project restart backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'
    docker compose -p $project restart frontend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:3000/'
    $afterRestartBody = Join-Path $work 'recipe-after-restart.json'
    $afterRestartStatus = Invoke-Status @('-s', '-o', $afterRestartBody, '-w', '%{http_code}', "http://127.0.0.1:8888/api/recipes/$recipeId", '-H', $auth)
    Assert-Equal $afterRestartStatus '200' 'mock recipe fetch after restart failed'
    $recipeVersionAfterRestart = (Get-Json $afterRestartBody).data.version
    Assert-Equal $recipeVersionAfterRestart 2 'mock recipe version did not survive restart'

    [PSCustomObject]@{
        registration_status = $registrationStatus
        model_provider = $model.data.provider
        recognition_status = $recognitionStatus
        recognition_images = $recognition.data.images.Count
        recognition_image_indexes = ($imageIndexes -join ',')
        confirmation_count = $confirmedCount
        fake_recipe_status = $recipeStatus
        fake_generator = $recipe.data.generator.is_mock
        nutrition_disclaimer = [bool]$recipe.data.nutrition_disclaimer
        recipe_version_after_chat = $recipeAfterChat.data.version
        sse_token = $hasToken
        sse_recipe_updated = $hasRecipeUpdated
        sse_done = $hasDone
        legacy_sse_events = $hasLegacyEvent
        history_total = $history.data.total
        dashboard_recipes = $dashboard.data.overview.recipes
        dashboard_chat_sessions = $dashboard.data.overview.chat_sessions
        ordinary_admin_api_status = $ordinaryAdminStatus
        recipe_version_after_restart = $recipeVersionAfterRestart
    } | ConvertTo-Json -Compress
}
finally {
    if ($work -and (Test-Path -LiteralPath $work)) { [IO.Directory]::Delete($work, $true) }
    $env:FOOD_PROVIDER = 'yolo'
    $env:FOOD_MODEL_PATH = '/models/food/best.pt'
    $env:FOOD_CLASSES_PATH = '/app/backend/scripts/food_model/classes.yaml'
    $env:FOOD_CONF_THRESHOLD = '0.25'
    $env:LLM_MODE = 'real'
    docker compose -p $project up -d --force-recreate backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'
    Pop-Location
}
