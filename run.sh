#!/bin/bash

cd "$HOME/skyscanner-optimum/" || exit
mkdir -p logs

# Init database monitoring tool
venv/bin/sqlite_web -H 0.0.0.0 -p 7070 db.sqlite3 &

# Start session makers
for i in {0..3}
do
  venv/bin/python -m api.maker config.json 2> "logs/log_maker$i.txt" &
done

# Start session pollers
for i in {0..9}
do
  venv/bin/python -m api.poller config.json 2> "logs/log_poller$i.txt" &
done

# Start bot
venv/bin/python bot.py 2> logs/log.txt &

# trap signal and wait children
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
wait