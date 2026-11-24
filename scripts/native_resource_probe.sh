#!/bin/sh
# Only fixed service names and filesystem paths are supplied by Compose.
mode=${1:-print}
service=${2:-}
state=${3:-running}
disk_path=${4:-/}
metrics_dir=/mice-metrics/samples

sample() {
    started=$(sed 's/^.*) //' /proc/1/stat 2>/dev/null | awk '{print $20}')
    printf 'at %s\ninstance %s-%s\nstate %s\n' "$(date +%s)" "$(hostname)" "$started" "$state"
    if [ -r /sys/fs/cgroup/cgroup.controllers ]; then
        awk '$1 == "usage_usec" {print "cpu_usec", $2}' /sys/fs/cgroup/cpu.stat 2>/dev/null
        awk '{print "cpu_quota", $1; print "cpu_period", $2}' /sys/fs/cgroup/cpu.max 2>/dev/null
        for field in memory.current memory.max memory.swap.current pids.current pids.max
        do
            if IFS= read -r value < "/sys/fs/cgroup/$field"; then
                printf '%s %s\n' "$field" "$value"
            fi
        done 2>/dev/null
    else
        awk '{printf "cpu_usec %.0f\n", $1 / 1000}' /sys/fs/cgroup/cpuacct/cpuacct.usage 2>/dev/null
        awk '{print "cpu_quota", $1}' /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null
        awk '{print "cpu_period", $1}' /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null
        awk '{print "memory.current", $1}' /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null
        awk '$1 < 9000000000000000000 {print "memory.max", $1}' /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null
        awk '{print "pids.current", $1}' /sys/fs/cgroup/pids/pids.current 2>/dev/null
        awk '{print "pids.max", $1}' /sys/fs/cgroup/pids/pids.max 2>/dev/null
    fi
    df -Pk "$disk_path" 2>/dev/null | awk 'NR == 2 {printf "disk_total %.0f\ndisk_used %.0f\ndisk_free %.0f\n", $2*1024, $3*1024, $4*1024}'
    if command -v nvidia-smi >/dev/null && command -v timeout >/dev/null; then
        timeout 2 nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu \
            --format=csv,noheader,nounits 2>/dev/null | head -n 16 | sed 's/^/gpu /'
    fi
}

case "$mode" in
    print) sample ;;
    store)
        case "$service" in ''|*[!a-z0-9-]*) exit 1 ;; esac
        # PostgreSQL's root healthcheck creates the sticky sample directory.
        # The reader mounts it read-only. Sandbox containers have no mount.
        if [ "$service" = db ] && [ ! -d "$metrics_dir" ]; then
            mkdir -p "$metrics_dir" && chmod 1777 "$metrics_dir" || exit 1
        fi
        tmp=$(mktemp "$metrics_dir/.$service.XXXXXX") || exit 1
        trap 'rm -f "$tmp"' EXIT
        sample > "$tmp" && chmod 644 "$tmp" && mv -f "$tmp" "$metrics_dir/$service"
        ;;
    *) exit 1 ;;
esac
