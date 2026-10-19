#!/bin/bash

BASE_PATH=data/pistachio/pipeline
FILEPATH=$BASE_PATH/data.standardized.csv

# Extract the header
head -n 1 $FILEPATH > $BASE_PATH/arrow.backward.csv
head -n 1 $FILEPATH > $BASE_PATH/arrow.forward.csv
head -n 1 $FILEPATH > $BASE_PATH/arrow.removed.csv
head -n 1 $FILEPATH > $BASE_PATH/tmp.csv

# Append matching lines (excluding header) to each file
tail -n +2 $FILEPATH | grep '<' >> $BASE_PATH/arrow.backward.csv
tail -n +2 $FILEPATH | grep -v '<' >> $BASE_PATH/tmp.csv
tail -n +2 $BASE_PATH/tmp.csv | grep "\\->" >> $BASE_PATH/arrow.forward.csv
tail -n +2 $BASE_PATH/tmp.csv | grep -v "\\->" >> $BASE_PATH/arrow.removed.csv

# Remove auxiliary csv
rm $BASE_PATH/tmp.csv
