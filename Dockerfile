FROM ubuntu:22.04

ENV DEBIAN_FRONTEND "noninteractive"

# System packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y wget unzip curl make gcc g++ xauth locales time vim git
# Install required Python packages via apt
RUN apt-get install -y python-is-python3  python3-pip python3-xarray python3-rasterio python3-geopandas python3-dask python3-sklearn python3-gdal

# Install AWS
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && ./aws/install && rm -fr ./aws

RUN mkdir /code
COPY . /code

RUN cd /code && pip3 install -r requirements.txt

ENTRYPOINT ["/code/scripts/run_tile_docker.sh"]
