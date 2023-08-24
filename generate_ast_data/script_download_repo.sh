#!/bin/bash
wget https://github.com/"$1"/archive/"$2".zip -P $3
unzip $3/"$2".zip -d $3
 