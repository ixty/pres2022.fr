#!/bin/bash
if [ ! -f "data/$1.db" ]; then
	echo "> processing $1..."
	source venv/bin/activate

	echo "> extracting archive..."
	7z x "../chétane-data-good/data-$1.7z"

	python -m chétane process $1
	rm -rf data-$1
	echo "> done"
else
	echo "> skipping $1"
fi
