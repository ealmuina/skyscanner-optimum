cd "$HOME/skyscanner-optimum/" || exit
(
  echo "$HOME/skyscanner-optimum/venv/bin/sqlite_web -H 0.0.0.0 -p 7070 db.sqlite3";
  echo "$HOME/skyscanner-optimum/venv/bin/python -m api.maker config.json 2> log_maker.txt"
  echo "$HOME/skyscanner-optimum/venv/bin/python -m api.poller config.json 2> log_poller.txt"
  echo "$HOME/skyscanner-optimum/venv/bin/python bot.py 2> log.txt"
) | parallel