FROM ubuntu:22.04

ENV DEBIAN_FRONTEND "noninteractive"

# System packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y wget unzip make gcc g++ xauth locales time vim git
# Install required Python packages via apt
RUN apt-get install -y python-is-python3  python3-pip python3-xarray python3-rasterio python3-geopandas python3-dask python3-sklearn python3-gdal

RUN mkdir /code
COPY . /code

RUN cd /code && pip3 install -r requirements.txt

ENTRYPOINT ["/code/scripts/le_lccs_png_level4.py"]
