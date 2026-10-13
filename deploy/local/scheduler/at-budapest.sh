#!/usr/bin/env bash
# Cron helper: runs COMMAND only when the current Europe/Budapest time is in one of HOURS (and on DAY), so a
# schedule is in Budapest time whatever the machine's time zone.
#
#   at-budapest.sh DAY HOURS COMMAND [ARGS...]
#     DAY    any, or one of mon tue wed thu fri sat sun (the Budapest weekday)
#     HOURS  comma-separated Budapest hours, 0-23 (e.g. 4,5)
#
# Why: Debian/Ubuntu cron ignores CRON_TZ (only cronie honours it), and a CRON_TZ line would also change the
# schedule of the user's own entries that follow it. install-linux.sh therefore writes crontab lines that fire
# every hour at the job's minute; this script lets one of them through in each scheduled Budapest hour and
# exits 0 silently otherwise. Daylight saving time needs no care: 03:00-23:59 exist exactly once every day.
# It needs the time zone database (tzdata): without it `TZ=Europe/Budapest date` silently gives UTC, so the
# script checks that the zone abbreviation is CET or CEST and fails loudly otherwise.
set -euo pipefail

usage() {
    printf 'usage: %s {any|mon|tue|wed|thu|fri|sat|sun} HOUR[,HOUR...] COMMAND [ARGS...]\n' "$0" >&2
    exit 2
}

[ $# -ge 3 ] || usage
day=$1
hours=$2
shift 2
case $day in
    any) want_day= ;;
    mon) want_day=1 ;;
    tue) want_day=2 ;;
    wed) want_day=3 ;;
    thu) want_day=4 ;;
    fri) want_day=5 ;;
    sat) want_day=6 ;;
    sun) want_day=7 ;;
    *) usage ;;
esac
case $hours in '' | ,* | *, | *,,* | *[!0-9,]*) usage ;; esac

# One date call, so weekday and hour come from the same instant. %u: 1 = Monday ... 7 = Sunday.
now=$(TZ=Europe/Budapest date '+%u %H %Z')
now_day=${now%% *}
rest=${now#* }
now_hour=${rest%% *}
zone=${rest#* }
case $zone in
    CET | CEST) ;;
    *)
        printf 'error: the time zone database has no Europe/Budapest (got zone %s); install tzdata\n' "$zone" >&2
        exit 1
        ;;
esac
now_hour=$((10#$now_hour)) # "04" -> 4 (a leading zero would otherwise mean octal)

[ -z "$want_day" ] || [ "$now_day" = "$want_day" ] || exit 0
match=0
old_ifs=$IFS
IFS=,
for hour in $hours; do
    [ "$((10#$hour))" -le 23 ] || usage
    if [ "$((10#$hour))" -eq "$now_hour" ]; then match=1; fi
done
IFS=$old_ifs
[ "$match" -eq 1 ] || exit 0
exec "$@"
