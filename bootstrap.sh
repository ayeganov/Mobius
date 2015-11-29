#!/usr/bin/env bash

# PostgreSQL requirement
sudo apt-get update

# Install C++
apt-get install -y g++ python-dev make git tig

# Install postgres
apt-get install -y postgresql-9.3 libpq-dev

# Google protobuf dependencies
apt-get install -y dh-autoreconf unzip

