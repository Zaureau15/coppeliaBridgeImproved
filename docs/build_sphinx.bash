# Run this from the root directory, not the docs directory.
# This command also runs on Windows if you have bash installed.
# It builds the docs, then opens them in your browser.
# Commend out the "start" line to stop the browser from auto-opening.

sphinx-build -b html docs docs/build/html
start docs/build/html/index.html
