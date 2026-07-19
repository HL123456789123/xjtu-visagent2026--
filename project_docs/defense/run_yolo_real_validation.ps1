$ErrorActionPreference = 'Stop'

# Runs against the local Compose project. Runtime credentials remain in .env and
# are never read, printed, or written by this script.
$project = 'visagent-history-dev'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Write-Utf8Json([string]$Path, $Value) {
    [IO.File]::WriteAllText(
        $Path,
        ($Value | ConvertTo-Json -Depth 10 -Compress),
        [Text.UTF8Encoding]::new($false)
    )
}

function Invoke-Status([string[]]$Arguments) {
    $status = & curl.exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed with exit code $LASTEXITCODE"
    }
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

function Get-Json([string]$Path) {
    return Get-Content -Raw -Encoding utf8 $Path | ConvertFrom-Json
}

Push-Location $root
$work = $null
try {
    $env:FOOD_PROVIDER = 'yolo'
    $env:FOOD_MODEL_PATH = '/models/food/best.pt'
    $env:FOOD_CLASSES_PATH = '/app/backend/scripts/food_model/classes.yaml'
    $env:FOOD_CONF_THRESHOLD = '0.25'
    $env:LLM_MODE = 'real'

    docker compose -p $project up -d --force-recreate backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'

    $suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
    $bytes = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $account = [ordered]@{
        username = "codexyolo$suffix"
        email = "codexyolo$suffix@example.com"
        password = [Convert]::ToBase64String($bytes).Replace('+', 'A').Replace('/', 'B').Replace('=', 'C')
    }
    $work = Join-Path $env:TEMP "visagent-yolo-$suffix"
    New-Item -ItemType Directory -Path $work | Out-Null
    $accountPath = Join-Path $work 'account.json'
    Write-Utf8Json $accountPath $account

    $registerBody = Join-Path $work 'register.json'
    $registrationStatus = Invoke-Status @('-s', '-o', $registerBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/auth/register', '-H', 'Content-Type: application/json', '--data-binary', "@$accountPath")
    Assert-Equal $registrationStatus '201' 'YOLO validation account registration failed'
    $loginBody = Join-Path $work 'login.json'
    $loginStatus = Invoke-Status @('-s', '-o', $loginBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/auth/login', '-H', 'Content-Type: application/json', '--data-binary', "@$accountPath")
    Assert-Equal $loginStatus '200' 'YOLO validation account login failed'
    $token = (Get-Json $loginBody).access_token
    Assert-True $token 'YOLO validation login did not return a token'
    $auth = "Authorization: Bearer $token"

    $modelBody = Join-Path $work 'model.json'
    $modelStatus = Invoke-Status @('-s', '-o', $modelBody, '-w', '%{http_code}', 'http://127.0.0.1:8888/api/food/model-status', '-H', $auth)
    Assert-Equal $modelStatus '200' 'YOLO model status failed'
    $model = Get-Json $modelBody
    Assert-Equal $model.data.provider 'yolo' 'model status did not identify YOLO'
    Assert-True $model.data.available 'YOLO model status reported unavailable'

    $png = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+T5Za8wAAAABJRU5ErkJggg==')
    [Array]::Resize([ref]$png, $png.Length - 8)
    $brokenPath = Join-Path $work 'truncated.png'
    [IO.File]::WriteAllBytes($brokenPath, $png)
    $invalidBody = Join-Path $work 'invalid.json'
    $invalidStatus = Invoke-Status @('-s', '-o', $invalidBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/food/recognitions', '-H', $auth, '-F', "images=@$brokenPath;type=image/png")
    Assert-Equal $invalidStatus '422' 'truncated image did not return 422'
    $invalidResponse = Get-Json $invalidBody
    Assert-Equal $invalidResponse.detail 'INVALID_IMAGE_CONTENT' 'truncated image returned the wrong error code'

    $imagePath = Join-Path $root 'frontend\public\food-carousel-1.jpg'
    $recognitionBody = Join-Path $work 'recognition.json'
    $recognitionStatus = Invoke-Status @('-s', '--max-time', '120', '-o', $recognitionBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/food/recognitions', '-H', $auth, '-F', "images=@$imagePath;type=image/jpeg", '-F', 'conf_threshold=0.25')
    Assert-Equal $recognitionStatus '201' 'YOLO recognition failed'
    $recognition = Get-Json $recognitionBody
    Assert-Equal $recognition.data.provider 'yolo' 'recognition response did not identify YOLO'
    Assert-True ($recognition.data.ingredients.Count -gt 0) 'YOLO produced no detections for the local demonstration image'
    $invalidBbox = @($recognition.data.ingredients | Where-Object { $_.bbox.x2 -le $_.bbox.x1 -or $_.bbox.y2 -le $_.bbox.y1 })
    Assert-Equal $invalidBbox.Count 0 'YOLO response contained an invalid bounding box'
    $imageIndexes = @($recognition.data.images | ForEach-Object { $_.image_index })
    Assert-Equal ($imageIndexes -join ',') '0' 'single YOLO upload did not preserve image_index 0'
    $recognitionId = $recognition.data.recognition_id

    $candidate = $recognition.data.ingredients[0]
    $confirmationPath = Join-Path $work 'confirmation.json'
    Write-Utf8Json $confirmationPath ([ordered]@{ ingredients = @(
        [ordered]@{ name = $candidate.display_name; class_name = $candidate.class_name; quantity = 1; unit = 'serving'; source = 'model' },
        [ordered]@{ name = 'egg'; class_name = $null; quantity = 2; unit = 'piece'; source = 'manual' }
    ) })
    $confirmationBody = Join-Path $work 'confirmation-response.json'
    $confirmationStatus = Invoke-Status @('-s', '-o', $confirmationBody, '-w', '%{http_code}', '-X', 'PUT', "http://127.0.0.1:8888/api/food/recognitions/$recognitionId/ingredients", '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$confirmationPath")
    Assert-Equal $confirmationStatus '200' 'ingredient confirmation failed'
    $confirmedCount = (Get-Json $confirmationBody).data.confirmed_ingredients.Count
    Assert-Equal $confirmedCount 2 'ingredient confirmation did not retain two entries'

    $recipePath = Join-Path $work 'recipe.json'
    Write-Utf8Json $recipePath ([ordered]@{ recognition_id = $recognitionId; preferences = [ordered]@{ servings = 2; taste = 'home-style'; max_time_minutes = 45; avoid_ingredients = @() } })
    $recipeBody = Join-Path $work 'recipe-response.json'
    $recipeStatus = Invoke-Status @('-s', '--max-time', '120', '-o', $recipeBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/recipes', '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$recipePath")
    Assert-Equal $recipeStatus '201' 'real LLM recipe generation failed'
    $recipe = Get-Json $recipeBody
    Assert-Equal $recipe.data.version 1 'real LLM recipe did not start at version 1'
    Assert-True (-not $recipe.data.generator.is_mock) 'recipe generation silently fell back to fake LLM'
    $recipeId = $recipe.data.recipe_id

    $sessionPath = Join-Path $work 'session.json'
    Write-Utf8Json $sessionPath ([ordered]@{ recipe_id = $recipeId })
    $sessionBody = Join-Path $work 'session-response.json'
    $sessionStatus = Invoke-Status @('-s', '-o', $sessionBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/chat/sessions', '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$sessionPath")
    Assert-Equal $sessionStatus '201' 'chat session creation failed'
    $sessionId = (Get-Json $sessionBody).data.session_id
    $messagePath = Join-Path $work 'message.json'
    Write-Utf8Json $messagePath ([ordered]@{ content = 'Please change this recipe to serve three people and use less oil.' })
    $ssePath = Join-Path $work 'chat-sse.txt'
    $sseStatus = Invoke-Status @('-sS', '--max-time', '180', '-o', $ssePath, '-w', '%{http_code}', '-N', '-X', 'POST', "http://127.0.0.1:8888/api/chat/sessions/$sessionId/messages", '-H', $auth, '-H', 'Content-Type: application/json', '--data-binary', "@$messagePath")
    Assert-Equal $sseStatus '200' 'real LLM chat stream failed'
    $sse = Get-Content -Raw -Encoding utf8 $ssePath
    $hasToken = $sse -match '(?m)^event: token$'
    $hasRecipeUpdated = $sse -match '(?m)^event: recipe_updated$'
    $hasDone = $sse -match '(?m)^event: done$'
    $hasLegacyEvent = $sse -match '(?m)^event: (message|chunk|complete)$'
    Assert-True ($hasToken -and $hasRecipeUpdated -and $hasDone -and -not $hasLegacyEvent) 'chat stream events did not satisfy the V1 contract'

    $recipeAfterChatBody = Join-Path $work 'recipe-after-chat.json'
    $recipeAfterChatStatus = Invoke-Status @('-s', '-o', $recipeAfterChatBody, '-w', '%{http_code}', "http://127.0.0.1:8888/api/recipes/$recipeId", '-H', $auth)
    Assert-Equal $recipeAfterChatStatus '200' 'recipe fetch after chat failed'
    $recipeAfterChat = Get-Json $recipeAfterChatBody
    Assert-Equal $recipeAfterChat.data.version 2 'chat update did not persist version 2'

    $historyBody = Join-Path $work 'history.json'
    $historyStatus = Invoke-Status @('-s', '-o', $historyBody, '-w', '%{http_code}', 'http://127.0.0.1:8888/api/recipes/history?page=1&page_size=20', '-H', $auth)
    Assert-Equal $historyStatus '200' 'history fetch failed'
    $history = Get-Json $historyBody
    Assert-True ($history.data.total -ge 1) 'history did not contain the persisted recipe'

    $dashboardBody = Join-Path $work 'dashboard.json'
    $dashboardStatus = Invoke-Status @('-s', '-o', $dashboardBody, '-w', '%{http_code}', 'http://127.0.0.1:8888/api/dashboard/food-stats', '-H', $auth)
    Assert-Equal $dashboardStatus '200' 'food dashboard fetch failed'
    $dashboard = Get-Json $dashboardBody
    Assert-True ($dashboard.data.overview.recipes -ge 1 -and $dashboard.data.overview.chat_sessions -ge 1) 'food dashboard did not aggregate the user recipe/chat data'
    $ordinaryAdminStatus = Invoke-Status @('-s', '-o', 'NUL', '-w', '%{http_code}', 'http://127.0.0.1:8888/api/admin/users', '-H', $auth)
    Assert-Equal $ordinaryAdminStatus '403' 'ordinary user admin API did not return 403'

    docker compose -p $project restart backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'
    docker compose -p $project restart frontend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:3000/'
    $afterRestartBody = Join-Path $work 'recipe-after-restart.json'
    $afterRestartStatus = Invoke-Status @('-s', '-o', $afterRestartBody, '-w', '%{http_code}', "http://127.0.0.1:8888/api/recipes/$recipeId", '-H', $auth)
    Assert-Equal $afterRestartStatus '200' 'recipe fetch after service restart failed'
    $recipeVersionAfterRestart = (Get-Json $afterRestartBody).data.version
    Assert-Equal $recipeVersionAfterRestart 2 'recipe version did not survive service restart'

    docker compose -p $project down | Out-Null
    docker compose -p $project up -d | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'
    Wait-HttpOk 'http://127.0.0.1:3000/'
    $afterDownUpBody = Join-Path $work 'recipe-after-down-up.json'
    $afterDownUpStatus = Invoke-Status @('-s', '-o', $afterDownUpBody, '-w', '%{http_code}', "http://127.0.0.1:8888/api/recipes/$recipeId", '-H', $auth)
    Assert-Equal $afterDownUpStatus '200' 'recipe fetch after compose down/up failed'
    $recipeVersionAfterDownUp = (Get-Json $afterDownUpBody).data.version
    Assert-Equal $recipeVersionAfterDownUp 2 'recipe version did not survive compose down/up'

    $env:FOOD_MODEL_PATH = '/models/food/not-present.pt'
    docker compose -p $project up -d --force-recreate backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'
    $unavailableBody = Join-Path $work 'unavailable.json'
    $unavailableStatus = Invoke-Status @('-s', '-o', $unavailableBody, '-w', '%{http_code}', '-X', 'POST', 'http://127.0.0.1:8888/api/food/recognitions', '-H', $auth, '-F', "images=@$imagePath;type=image/jpeg")
    Assert-Equal $unavailableStatus '503' 'missing YOLO weight did not return 503'

    $env:FOOD_MODEL_PATH = '/models/food/best.pt'
    docker compose -p $project up -d --force-recreate backend | Out-Null
    Wait-HttpOk 'http://127.0.0.1:8888/api/health'
    $finalRecipeBody = Join-Path $work 'recipe-final.json'
    $finalRecipeStatus = Invoke-Status @('-s', '-o', $finalRecipeBody, '-w', '%{http_code}', "http://127.0.0.1:8888/api/recipes/$recipeId", '-H', $auth)
    Assert-Equal $finalRecipeStatus '200' 'recipe fetch after restoring YOLO failed'
    $finalRecipeVersion = (Get-Json $finalRecipeBody).data.version
    Assert-Equal $finalRecipeVersion 2 'recipe version changed after restoring YOLO'

    [PSCustomObject]@{
        registration_status = $registrationStatus
        model_provider = $model.data.provider
        model_available = $model.data.available
        model_class_count = $model.data.class_count
        invalid_image_status = $invalidStatus
        invalid_image_detail = $invalidResponse.detail
        recognition_status = $recognitionStatus
        recognition_images = $recognition.data.images.Count
        recognition_image_indexes = ($imageIndexes -join ',')
        yolo_detection_count = $recognition.data.ingredients.Count
        valid_bboxes = $true
        confirmation_count = $confirmedCount
        real_llm_recipe_status = $recipeStatus
        real_llm_generator_mock = $recipe.data.generator.is_mock
        recipe_version_after_chat = $recipeAfterChat.data.version
        sse_token = $hasToken
        sse_recipe_updated = $hasRecipeUpdated
        sse_done = $hasDone
        legacy_sse_events = $hasLegacyEvent
        ordinary_admin_api_status = $ordinaryAdminStatus
        history_total = $history.data.total
        dashboard_recipes = $dashboard.data.overview.recipes
        dashboard_chat_sessions = $dashboard.data.overview.chat_sessions
        recipe_version_after_restart = $recipeVersionAfterRestart
        recipe_version_after_down_up = $recipeVersionAfterDownUp
        missing_weight_status = $unavailableStatus
        final_recipe_version = $finalRecipeVersion
    } | ConvertTo-Json -Compress
}
finally {
    if ($work -and (Test-Path -LiteralPath $work)) {
        [IO.Directory]::Delete($work, $true)
    }
    Pop-Location
}
