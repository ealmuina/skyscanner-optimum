(
  echo "sqlite_web -H 0.0.0.0 -p 7070 $HOME/skyscanner-optimum/db.sqlite3";
  echo "python3 bot.py 2> $HOME/skyscanner-optimum/log.txt"
) | parallel