$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$renderer = Join-Path $skillRoot 'scripts\render_rough_cut.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('openmontage-rough-cut-test-' + [guid]::NewGuid())

try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $sourceA = Join-Path $tempRoot '01.MOV'
    $sourceB = Join-Path $tempRoot '02.MOV'
    New-Item -ItemType File -Path $sourceA | Out-Null
    New-Item -ItemType File -Path $sourceB | Out-Null

    $edlPath = Join-Path $tempRoot 'edl.json'
    $outputPath = Join-Path $tempRoot 'rough-cut.mp4'
    @{
        version = 'rough-cut-v1'
        segments = @(
            @{ order = 1; input_path = $sourceA; start_seconds = 1.0; end_seconds = 3.0; reason = 'keep complete take' },
            @{ order = 2; input_path = $sourceB; start_seconds = 4.0; end_seconds = 5.5; reason = 'remove repeated start' }
        )
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $edlPath -Encoding utf8

    $json = & $renderer -EdlPath $edlPath -OutputPath $outputPath -PlanOnly | ConvertFrom-Json

    if ($json.segment_count -ne 2) { throw "Expected 2 segments, got $($json.segment_count)" }
    if ([math]::Abs([double]$json.estimated_duration_seconds - 3.5) -gt 0.001) {
        throw "Expected duration 3.5, got $($json.estimated_duration_seconds)"
    }
    if ($json.output_path -ne $outputPath) { throw 'Output path was not preserved.' }
    if ($json.video_encoder_candidates[0] -ne 'h264_qsv') { throw 'Hardware encoder must be preferred.' }
    if ($json.video_encoder_candidates[1] -ne 'libx264') { throw 'CPU fallback must be available.' }

    Write-Output 'PASS: render_rough_cut PlanOnly contract'
}
finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
