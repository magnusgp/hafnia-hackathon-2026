$ErrorActionPreference = 'Stop'
Import-Module MilestonePSTools
$names = @('vehicle_breakdown_traffic_queue', 'bin_pushed_over_onto_sidewalk',
    'escooter_left_across_sidewalk', 'school_gate_break_in_night',
    'graffiti_on_standing_train', 'busy_street', 'traffic_flows_in_the_open_lanes')
foreach ($name in $names) {
    & "$PSScriptRoot\..\acquire_recording.ps1" -CameraName $name -Seconds 60 -Interval 1
}
