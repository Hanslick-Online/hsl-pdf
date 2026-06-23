#!/bin/bash
rm -rf ./data

# fetch edition traktat
wget https://github.com/Hanslick-Online/hsl-vms-data/archive/refs/heads/master.zip
unzip master
mkdir -p ./data/traktat/editions
mkdir ./data/traktat/comp
mkdir ./data/meta
mv hsl-vms-data-master/102_derived_tei/102_02_tei-simple_refactored/*.xml ./data/traktat/editions
#mv hsl-vms-data-master/102_derived_tei/102_05_comp_refactored/*.xml ./data/traktat/comp
#mv hsl-vms-data-master/102_derived_tei/102_06_paratexts/*.xml ./data/meta
rm -rf hsl-vms-data-master
rm master.zip

# fetch edition critics
wget https://github.com/Hanslick-Online/hsl-data-ct/archive/refs/heads/main.zip
unzip main
mkdir -p ./data/critics/editions
mv hsl-data-ct-main/data/editions/*.xml ./data/critics/editions
#mv hsl-data-ct-main/data/meta/*.xml ./data/meta
rm -rf hsl-data-ct-main
rm main.zip

# fetch edition data-vms
wget https://github.com/Hanslick-Online/hsl-data-vms/archive/refs/heads/main.zip
unzip main
mkdir -p ./data/vms/editions
mv hsl-data-vms-main/data/editions/*.xml ./data/vms/editions
rm main.zip

# fetch docs about VMS
wget https://github.com/Hanslick-Online/hsl-vms-docs/archive/refs/heads/main.zip
unzip main
mkdir -p ./data/doc/editions
mv hsl-vms-docs-main/data/editions/*.xml ./data/doc/editions
#mv hsl-vms-docs-main/data/meta/*.xml ./data/meta
rm -rf hsl-vms-docs-main
rm main.zip

# fetch edition entities all
#rm -rf ./data/indices
#mkdir ./data/indices
#rm -rf ./html/geo
#mkdir ./html/geo
#wget https://github.com/Hanslick-Online/hsl-entities/archive/refs/heads/main.zip
#unzip main
#mv hsl-entities-main/out/*.xml ./data/indices
#mv hsl-entities-main/out/*.geojson ./html/geo
#rm -rf hsl-entities-main
#rm main.zip

#./build_app/python/number_paragraphs.py data/{doc,critics,vms}/editions/*xml
