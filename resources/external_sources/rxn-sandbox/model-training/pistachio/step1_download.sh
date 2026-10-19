#!/bin/bash

BASE_URL=https://www.nextmovesoftware.com/downloads/pistachio/releases/
RELEASE=2025Q2
curl -L -C - --user <USER>:<PASSWORD> $BASE_URL/$RELEASE/data/pistachio.tar.gz -o pistachio.tar.gz
