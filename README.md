# PDF-Editions of


* data is fetched from https://github.com/Hanslick-Online/hsl-vms-data
* build with [DSE-Static-Cookiecutter](https://github.com/acdh-oeaw/dse-static-cookiecutter)


## initial (one time) setup

* run `./fetch_data.sh`
* run `ant`

> [!NOTE]
> The `build.xml` triggered by the `ant` command presumes the following folder-file structure in the data repo:
> 
> ```
> data/
> ├── editions/
> │   ├── *.xml
> │   ├── *.xml
> │   └── *.xml
> ├── indices/
> │   ├── listbibl.xml
> │   ├── listorg.xml
> │   ├── listperson.xml
> │   └── listplace.xml
> └── meta/
>     └── about.xml
> ```
> 
> Otherwise, modify the relevant lines of the `build.xml`.

## set up GitHub repo
* create a public, new, and empty (without README, .gitignore, license) GitHub repo https://github.com/Hanslick-Online/hsl-pdf 
* run `git init` in the root folder of your application hsl-pdf
* execute the commands described under `…or push an existing repository from the command line` in your new created GitHub repo https://github.com/Hanslick-Online/hsl-pdf

## start dev server

* `cd html/`
* `uv run -m http.server`
* go to [http://0.0.0.0:8000/](http://0.0.0.0:8000/)

## publish as GitHub Page

* go to https://https://github.com/Hanslick-Online/hsl-pdf/actions/workflows/build.yml
* click the `Run workflow` button

## Python scripting
The project uses [uv](https://docs.astral.sh/uv/), as Python package and project manager.


## dockerize your application

* To build the image run: `docker build -f docker/Dockerfile -t hsl-pdf .`
* To run the container: `docker run -p 80:80 --rm --name hsl-pdf hsl-pdf`

## Licenses

This project is released under the [MIT License](LICENSE)

### third-party JavaScript libraries
The code for all third-party JavaScript libraries used is included in the `html/vendor` folder, their respective licenses can be found either in a `LICENSE.txt` file or directly in the header of the `.js` file

### SAXON-HE
The projects also includes Saxon-HE, which is licensed separately under the Mozilla Public License, Version 2.0 (MPL 2.0). See the dedicated [LICENSE.txt](saxon/notices/LICENSE.txt)

