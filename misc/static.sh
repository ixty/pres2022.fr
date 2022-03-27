#!/bin/bash
set -e

# env setup
cd "$(dirname "$0")"
source venv/bin/activate

# start local web server
python -m chétane server &
pid=$!
sleep 3

# start web sync
wget -q --mirror --adjust-extension --page-requisites http://127.0.0.1:8080/
rm -rf static
mv '127.0.0.1:8080' static

# stop web server
kill $pid

# done
echo "> done $(date)"
