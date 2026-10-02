#!/bin/bash
# JobRadar cron wrapper — reads config.yaml to check if feature is enabled
# Usage: cron_wrapper.sh alert|digest
# Cron runs this at fixed times; the wrapper checks config for enabled + time match

set -euo pipefail

MODE="${1:-}"
CONFIG="/local/docker/jobradar/config.yaml"
LOG_DIR="/local/docker/jobradar/data"
CONTAINER="jobradar"

if [ -z "$MODE" ] || [[ "$MODE" != "alert" && "$MODE" != "digest" ]]; then
    echo "Usage: $0 alert|digest"
    exit 1
fi

# Parse config.yaml with python
RESULT=$(python3 -c "
import yaml, sys, datetime
cfg = yaml.safe_load(open('$CONFIG'))
sched = cfg.get('schedule', {})
section = sched.get('$MODE', {})
if not section.get('enabled', False):
    print('DISABLED')
    sys.exit(0)
# Check time match (within 30-min window for cron precision)
cfg_time = section.get('time', '07:00')
now = datetime.datetime.now()
try:
    h, m = map(int, cfg_time.split(':'))
    cfg_hour = h
except:
    cfg_hour = 7
# For digest, also check day-of-week
if '$MODE' == 'digest':
    day_map = {'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5,'sunday':6}
    cfg_day = day_map.get(section.get('day', 'monday').lower(), 0)
    if now.weekday() != cfg_day:
        print('WRONG_DAY')
        sys.exit(0)
# Check hour match (cron runs at top of hour, check ±1 tolerance)
if abs(now.hour - cfg_hour) > 1:
    print('WRONG_TIME')
    sys.exit(0)
print('RUN')
" 2>&1)

echo "$(date '+%Y-%m-%d %H:%M:%S') [$MODE] config check: $RESULT"

if [ "$RESULT" != "RUN" ]; then
    exit 0
fi

# Run the command in the container
echo "$(date '+%Y-%m-%d %H:%M:%S') [$MODE] running docker exec..."
if [ "$MODE" = "alert" ]; then
    docker exec "$CONTAINER" python -m jobradar.main alert 2>&1
elif [ "$MODE" = "digest" ]; then
    docker exec "$CONTAINER" python -m jobradar.main digest 2>&1
fi
echo "$(date '+%Y-%m-%d %H:%M:%S') [$MODE] done"

