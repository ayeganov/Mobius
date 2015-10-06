#!/usr/bin/env bash

# PostgreSQL requirement
sudo apt-get update

function install_google_proto_buf
{
    pushd /tmp
    git clone https://github.com/GreatFruitOmsk/protobuf-py3.git
    pushd protobuf-py3
    ./autogen.sh
    ./configure --prefix=/usr
    make
    make check
    sudo make install

    pushd python
    python3 setup.py build
    python3 setup.py test && sudo python3 setup.py install
}

# Install C++
apt-get install -y g++ python-dev make git tig

# Install postgres
apt-get install -y postgresql-9.3 python-dev libpq-dev

# Google protobuf dependencies
apt-get install -y dh-autoreconf unzip

# Install python 3 and all libraries we'll need
apt-get install -y python3 python3-pip
pip3 install -r /vagrant/requirements.txt

install_google_proto_buf
