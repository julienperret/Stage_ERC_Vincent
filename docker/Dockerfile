# Download base image debian stretch
FROM debian:stretch

# Add GPG to be able to add key from keyserver
RUN apt-get update
RUN apt-get -y install gnupg2 apt-transport-https
# Add QGIS debian repository and its key
RUN echo "deb     http://qgis.org/debian stretch main" >> /etc/apt/sources.list
RUN gpg --keyserver keyserver.ubuntu.com --recv CAEB3DC3BDF7FB45
RUN gpg --export --armor CAEB3DC3BDF7FB45 | apt-key add -

# Update Software repository
RUN apt-get update

# Install necessary dependencies from repository
RUN apt-get install -y qgis python-qgis python-gdal python3-gdal python3-numpy python3-pandas python3-xlrd xvfb

# Create work directory
RUN mkdir -p /app
WORKDIR /app/

# Copy python files to work directory
COPY ../utils/insee_to_csv.py /app
COPY ../utils/magic.py /app
COPY ../utils/tif_to_gif.py /app
COPY ../prepare.py /app
COPY ../simulate.py /app
COPY ../toolbox.py /app
