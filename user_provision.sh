#!/usr/bin/env bash

function install_google_proto_buf
{
    pushd /tmp
    git clone https://github.com/GreatFruitOmsk/protobuf-py3.git
    pushd protobuf-py3
    ./autogen.sh
    ./configure --prefix=${HOME}/.pyenv/versions/3.4.3
    make -j5
    make check -j5
    sudo make install

    pushd python
    $(pyenv which python) setup.py build
    $(pyenv which python) setup.py test && sudo $(pyenv which python) setup.py install

    popd
    popd
    popd
}

# Install python 3 and all libraries we'll need through pyenv
curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bash_profile
echo 'eval "$(pyenv init -)"' >> ~/.bash_profile
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bash_profile

pyenv install 3.4.3
pyenv global 3.4.3
pip3 install -r /vagrant/requirements.txt

install_google_proto_buf
