#!/bin/bash -e

ID_NAME=$(python3 -c "import json; print(json.load(open('plugin.json'))['identifier'])")

if [ -z "$ID_NAME" ]; then
    echo "Error: Could not extract identifier from plugin.json"
    exit 1
fi

echo "Detected Identifier: $ID_NAME"

DIR_INSTALL=${ID_NAME//./_}
TEMP_NAME=${ID_NAME##*.}
DIR_INSTALL_DEV=${TEMP_NAME//-/_}
PATH_INSTALL_PLUGIN="$HOME/.local/share/kicad/9.0/3rdparty/plugins/"
PATH_INSTALL_RESOURCE="$HOME/.local/share/kicad/9.0/3rdparty/resources/"
PATH_INSTALL_DEV="$HOME/.local/share/kicad/9.0/plugins/"
FULL_PLUGIN="$PATH_INSTALL_PLUGIN$DIR_INSTALL"
FULL_RESOURCE="$PATH_INSTALL_RESOURCE$DIR_INSTALL"
FULL_DEV="$PATH_INSTALL_DEV$DIR_INSTALL_DEV"

install() {
    if [ -d "$FULL_PLUGIN" ]; then
        rm -rf $FULL_PLUGIN
    fi

    if [ -d "$FULL_RESOURCE" ]; then
        rm -rf $FULL_RESOURCE
    fi

    mkdir $FULL_PLUGIN
    mkdir $FULL_RESOURCE
    cp icons/icon_64x64.png $FULL_RESOURCE/icon.png
    cp icon.png $FULL_PLUGIN
    cp plugin.json $FULL_PLUGIN
    cp *.py $FULL_PLUGIN
    cp requirements.txt $FULL_PLUGIN
    cp package.json $FULL_PLUGIN
    cp -r preview/ $FULL_PLUGIN
}

install_dev() {
    if [ -d "$FULL_DEV" ]; then
        rm -rf $FULL_DEV
    fi
    mkdir $FULL_DEV

    cp icon.png $FULL_DEV
    cp plugin.json $FULL_DEV
    cp *.py $FULL_DEV
    cp requirements.txt $FULL_DEV
    cp package.json $FULL_DEV
    cp -r preview/ $FULL_DEV
}

uninstall() {
    if [ -d "$FULL_PLUGIN" ]; then
        rm -rf $FULL_PLUGIN
    fi

    if [ -d "$FULL_RESOURCE" ]; then
        rm -rf $FULL_RESOURCE
    fi

    if [ -d "$FULL_DEV" ]; then
        rm -rf $FULL_DEV
    fi
}

release() {
    version=$(grep "version =" version.py | cut -d"'" -f2)
    name=$(echo $TEMP_NAME-$version.zip)

    echo "Building release $version"
    cp metadata_template.json metadata.json
    sed -i -e "s/VERSION/$version/g" metadata.json
    sed -i '/download_/d' metadata.json
    sed -i '/install_size/d' metadata.json

    mkdir resources
    cp icons/icon_64x64.png resources/icon.png

    mkdir -p plugins
    cp icon.png plugins/
    cp plugin.json plugins/
    cp *.py plugins/
    cp requirements.txt plugins/
    cp package.json plugins/
    cp -r preview/ plugins/

    zip -r $name plugins resources metadata.json

    rm -rf plugins
    rm -rf resources

    sha=$(sha256sum $name | cut -d' ' -f1)
    size=$(du -b $name | cut -f1)
    installSize=$(unzip -l $name | tail -1 | xargs | cut -d' ' -f1)

    cp metadata_template.json metadata.json
    sed -i -e "s/VERSION/$version/g" metadata.json
    sed -i -e "s/SHA256/$sha/g" metadata.json
    sed -i -e "s/DOWNLOAD_SIZE/$size/g" metadata.json
    sed -i -e "s/INSTALL_SIZE/$installSize/g" metadata.json

    mv $name pcm/
}

if [ "$1" = "install" ] ; then
    echo "install"
    install
    exit
fi

if [ "$1" = "install-dev" ] ; then
    echo "install-dev"
    install_dev
    exit
fi

if [ "$1" = "uninstall" ] ; then
    echo "uninstall"
    uninstall
    exit
fi

if [ "$1" = "release" ] ; then
    echo "release"
    release
    exit
fi