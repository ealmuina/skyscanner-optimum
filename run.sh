cd "$HOME/skyscanner-optimum/" || exit
(
  echo "sqlite_web -H 0.0.0.0 -p 7070 db.sqlite3";
  echo "python3 bot.py >log.txt 2>&1"
) | parallel