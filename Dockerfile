 # Download base image debian stretch
FROM debian:stretch

# Add GPG to be able to add key from keyserver
RUN apt-get update
RUN apt-get -y install gnupg2 apt-transport-https
# Add QGIS debian repository and its key
RUN echo "deb     http://qgis.org/debian stretch main" >> /etc/apt/sources.list
RUN gpg --keyserver keyserver.ubuntu.com  --recv CAEB3DC3BDF7FB45
#RUN gpg --keyserver keyserver.ubuntu.com --keyserver-options  http-proxy=http://proxy.ign.fr:3128  --keyserver-options  https-proxy=https://proxy.ign.fr:3128 --recv CAEB3DC3BDF7FB45
RUN gpg --export --armor CAEB3DC3BDF7FB45 | apt-key add -

# Update Software repository
RUN apt-get update

# Install necessary dependencies from repository
RUN apt-get install -y qgis python-qgis python-gdal python3-gdal python3-numpy python3-pandas python3-xlrd xvfb

## Set a default user. Available via runtime flag `--user docker` 
## Add user to 'staff' group
## Create work directory
RUN useradd docker \
	&& mkdir /home/docker \
	&& mkdir /home/docker/app \
	&& mkdir /home/docker/data \
	&& addgroup docker staff

WORKDIR /home/docker/app

# Copy python files to work directory
COPY /utils/insee_to_csv.py /home/docker/app
COPY /utils/magic.py /home/docker/app
COPY /utils/tif_to_gif.py /home/docker/app
COPY /prepare.py /home/docker/app
COPY /simulate.py /home/docker/app
COPY /toolbox.py /home/docker/app

RUN chown -R docker:docker /home/docker
