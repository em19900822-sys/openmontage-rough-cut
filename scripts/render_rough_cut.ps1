param(
    [Parameter(Mandatory = $true)]
    [string]$EdlPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [ValidateSet('auto', 'h264_qsv', 'libx264')]
    [string]$Encoder = 'auto',

    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'

function Convert-ToInvariantNumber([double]$Value) {
    return [string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0:0.###}', $Value)
}

function Test-CommandAvailable([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Path -LiteralPath $EdlPath -PathType Leaf)) {
    throw "EDL not found: $EdlPath"
}

$edl = Get-Content -Raw -LiteralPath $EdlPath | ConvertFrom-Json
$segments = @($edl.segments | Sort-Object { [int]$_.order })
if ($segments.Count -eq 0) { throw 'EDL contains no segments.' }

$seenOrders = @{}
$duration = 0.0
foreach ($segment in $segments) {
    $order = [int]$segment.order
    if ($seenOrders.ContainsKey($order)) { throw "Duplicate segment order: $order" }
    $seenOrders[$order] = $true

    if (-not $segment.input_path) { throw "Segment $order has no input_path." }
    if (-not (Test-Path -LiteralPath $segment.input_path -PathType Leaf)) {
        throw "Segment source not found: $($segment.input_path)"
    }

    $start = [double]$segment.start_seconds
    $end = [double]$segment.end_seconds
    if ($start -lt 0 -or $end -le $start) {
        throw "Invalid range for segment ${order}: $start-$end"
    }
    $duration += $end - $start
}

$encoderCandidates = switch ($Encoder) {
    'h264_qsv' { @('h264_qsv') }
    'libx264' { @('libx264') }
    default { @('h264_qsv', 'libx264') }
}

$plan = [ordered]@{
    edl_path = [IO.Path]::GetFullPath($EdlPath)
    output_path = [IO.Path]::GetFullPath($OutputPath)
    segment_count = $segments.Count
    estimated_duration_seconds = [math]::Round($duration, 3)
    video_encoder_candidates = $encoderCandidates
    subtitles = $false
    beauty = $false
    transition = 'hard_cut'
}

if ($PlanOnly) {
    $plan | ConvertTo-Json -Depth 5
    exit 0
}

if (-not (Test-CommandAvailable 'ffmpeg')) { throw 'ffmpeg is unavailable.' }
if (-not (Test-CommandAvailable 'ffprobe')) { throw 'ffprobe is unavailable.' }

$outputFullPath = [IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $outputFullPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$sourcePaths = [System.Collections.Generic.List[string]]::new()
foreach ($segment in $segments) {
    $full = [IO.Path]::GetFullPath([string]$segment.input_path)
    if (-not $sourcePaths.Contains($full)) { $sourcePaths.Add($full) }
}

$baseArgs = @('-hide_banner', '-loglevel', 'warning', '-y')
foreach ($source in $sourcePaths) { $baseArgs += @('-i', $source) }

$filterParts = @()
$concatInputs = @()
for ($i = 0; $i -lt $segments.Count; $i++) {
    $segment = $segments[$i]
    $sourceFull = [IO.Path]::GetFullPath([string]$segment.input_path)
    $inputIndex = $sourcePaths.IndexOf($sourceFull)
    $start = Convert-ToInvariantNumber ([double]$segment.start_seconds)
    $end = Convert-ToInvariantNumber ([double]$segment.end_seconds)
    $filterParts += "[$inputIndex`:v]trim=start=$start`:end=$end,setpts=PTS-STARTPTS[v$i]"
    $filterParts += "[$inputIndex`:a]atrim=start=$start`:end=$end,asetpts=PTS-STARTPTS[a$i]"
    $concatInputs += "[v$i][a$i]"
}
$filter = ($filterParts -join ';') + ';' + ($concatInputs -join '') + "concat=n=$($segments.Count)`:v=1`:a=1[v][a]"

$usedEncoder = $null
$lastExitCode = 1
foreach ($candidate in $encoderCandidates) {
    if (Test-Path -LiteralPath $outputFullPath) { Remove-Item -LiteralPath $outputFullPath -Force }
    $args = @($baseArgs) + @('-filter_complex', $filter, '-map', '[v]', '-map', '[a]')
    if ($candidate -eq 'h264_qsv') {
        $args += @('-c:v', 'h264_qsv', '-preset', 'veryfast', '-global_quality', '22', '-look_ahead', '0', '-profile:v', 'high')
    }
    else {
        $args += @('-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-profile:v', 'high')
    }
    $args += @('-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', $outputFullPath)

    & ffmpeg @args
    $lastExitCode = $LASTEXITCODE
    if ($lastExitCode -eq 0 -and (Test-Path -LiteralPath $outputFullPath -PathType Leaf)) {
        $usedEncoder = $candidate
        break
    }
}

if (-not $usedEncoder) { throw "Render failed with exit code $lastExitCode." }

$probeRaw = & ffprobe -v error -show_entries 'format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels' -of json -- $outputFullPath
if ($LASTEXITCODE -ne 0) { throw 'ffprobe verification failed.' }
$probe = $probeRaw | ConvertFrom-Json
$video = @($probe.streams | Where-Object codec_type -eq 'video')
$audio = @($probe.streams | Where-Object codec_type -eq 'audio')
if ($video.Count -ne 1 -or $audio.Count -ne 1) { throw 'Output must contain one video stream and one audio stream.' }

& ffmpeg -v error -i $outputFullPath -map '0:v:0' -map '0:a:0' -f null NUL
if ($LASTEXITCODE -ne 0) { throw 'Full decode verification failed.' }

$actualDuration = [double]$probe.format.duration
if ([math]::Abs($actualDuration - $duration) -gt 1.0) {
    throw "Output duration mismatch. Expected about $duration seconds, got $actualDuration."
}

[ordered]@{
    status = 'pass'
    output_path = $outputFullPath
    segment_count = $segments.Count
    expected_duration_seconds = [math]::Round($duration, 3)
    actual_duration_seconds = [math]::Round($actualDuration, 3)
    size_bytes = [long]$probe.format.size
    video_encoder = $usedEncoder
    video_codec = $video[0].codec_name
    width = $video[0].width
    height = $video[0].height
    fps = $video[0].r_frame_rate
    audio_codec = $audio[0].codec_name
    sample_rate = $audio[0].sample_rate
    channels = $audio[0].channels
    full_decode = 'pass'
} | ConvertTo-Json -Depth 5
