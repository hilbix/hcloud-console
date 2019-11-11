#!/bin/bash

STDOUT() { local e=$?; printf '%q' "$1"; [ 1 -ge "$#" ] || printf ' %q' "${@:2}"; printf '\n'; return $e; }
STDERR() { STDOUT "$@" >&2; }
OOPS() { STDERR OOPS: "$@"; exit 23; }
x() { STDERR exec: "$@"; "$@"; set -- $? "$@"; STDERR "ret$1:" "${@:2}"; return $1; }
o() { x "$@" || OOPS fail $?: "$@"; }
UNLESS() { local e=$?; [ ".$1" = ".$2" ] || "${@:3}"; return $e; }
v() { local -n ___v="$1"; ___v="$("${@:2}")" || UNLESS x "$2" OOPS fail $?: "${@:2}"; }

v ME readlink -e -- "$0"
v MYSTATE stat -- "$ME"

DIR="$ME"
while	DIR="${DIR%/*}"
	SCRIPT="$DIR/server.py"
	[ ! -x "$SCRIPT" ] && [ -n "$DIR" ] && [ ".$LAST" != ".$DIR" ]
do	LAST="$DIR"; done

test -x "$SCRIPT" || v SCRIPT which server.py
o test -x "$SCRIPT"

o "$SCRIPT" list

cmd()
{
echo "cmd: $1 $2"
"$SCRIPT" "$1" "$2"
}

# Note: This restarts automatically if edited
maintainance()
{
test ".$MYSTATE" = ".$(stat -- "$ME")" || OOPS I have changed, CU
have=false
while	cmd="$("$SCRIPT" pull)"
do
	arg="${cmd#* }"
	case "$cmd" in
	('sync '*)	cmd sync "$arg";;
	('start '*)	cmd start "$arg";;
	('stop '*)	cmd stop "$arg";;
	('console '*)	cmd console "$arg";;
	('new '*)	cmd create "$arg";;
	('kill '*)	cmd kill "$arg";;
	('off '*)	cmd force "$arg";;
	('reset '*)	cmd reset "$arg";;
	(*)		printf 'UNKNOWN: %q\n' "$cmd"; continue;;
	esac
	have=:
done
$have || o "$SCRIPT" sync
}

# Do the maintainance each "$1" seconds or when events arrive
run()
{
coproc exec python3 "$SCRIPT" wait ''
trap 'x kill $COPROC_PID' 0

while	while read -ru${COPROC[0]} -t.001; do :; done
	maintainance
do
	read -ru${COPROC[0]} -t${1:-20}
	# terminate on RETURN
	read -rt0.01 && exit
done

x kill $COPROC_PID
trap '' 0
}

# Loop until we see a RETURN on the console
# This delays 1s in case there is some catastrophic failure in "run"
# as "run" should only loop on error (like desynchronization or
# MongoDB goes away or similar)
loop()
{
while	date && ! read -t1
do
	run "$@"
done
}

# Note: This restarts automatically if edited
loop "$@"

