# Optional: run Hindsight TUI explorer (or UI) with API URL from env or default.
# Requires Hindsight CLI: https://hindsight.vectorize.io/sdks/cli
# Banks for RadioShaq are named radioshaq-{CALLSIGN} (e.g. radioshaq-W1ABC).

$url = $env:HINDSIGHT_API_URL
if (-not $url) { $url = $env:RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL }
if (-not $url) { $url = "http://localhost:8888" }

$env:HINDSIGHT_API_URL = $url
Write-Host "Using HINDSIGHT_API_URL=$url"
$mode = $args[0]
if ($mode -eq "ui") {
    hindsight ui
} else {
    hindsight explore
}
